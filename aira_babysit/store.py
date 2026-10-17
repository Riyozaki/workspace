"""Durable SQLite run registry, transactional checkpoints and append-only events."""
from __future__ import annotations
import contextlib,hashlib,json,os,sqlite3,time,uuid
from pathlib import Path
from .config import DEFAULT_RUNS,RunConfig,canonical,frozen_sources,safe_id
from .tasks import make_tasks


class Store:
 def __init__(self,root=DEFAULT_RUNS):
  self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True);self.db=self.root/'runs.sqlite3'
  with self.connect() as c:
   c.executescript('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,spec TEXT NOT NULL,spec_sha TEXT NOT NULL,status TEXT NOT NULL,control TEXT NOT NULL DEFAULT '',active_seconds REAL NOT NULL DEFAULT 0,recovery_charge REAL NOT NULL DEFAULT 0,owner_pid INTEGER,owner_token TEXT,lease_until REAL,heartbeat REAL,created REAL,updated REAL,error TEXT);
CREATE TABLE IF NOT EXISTS episodes(run_id TEXT,task_id TEXT,record TEXT NOT NULL,PRIMARY KEY(run_id,task_id));
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,utc_unix REAL,kind TEXT,payload TEXT);''')
 @contextlib.contextmanager
 def connect(self):
  c=sqlite3.connect(self.db,timeout=10,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA busy_timeout=10000')
  try:yield c
  finally:c.close()
 def path(self,rid):return self.root/safe_id(rid)
 def event(self,rid,kind,**payload):
  with self.connect() as c:c.execute('INSERT INTO events(run_id,utc_unix,kind,payload) VALUES(?,?,?,?)',(rid,time.time(),kind,canonical(payload)))
 def create(self,config):
  config.validate();rid=uuid.uuid4().hex[:16];path=self.path(rid);path.mkdir()
  pools={s:make_tasks(config.max_examples if s=='train' else 6,config.seed,s) for s in ('train','development','holdout')}
  for s,rows in pools.items():(path/f'{s}.jsonl').write_text(''.join(canonical(r)+'\n' for r in rows))
  hashes={s:hashlib.sha256((path/f'{s}.jsonl').read_bytes()).hexdigest() for s in pools}
  from aira_local.engine import SYSTEM
  spec={'serving_system_prompt':SYSTEM,'version':1,'config':config.to_dict(),'sources':frozen_sources(),'pool_sha256':hashes,'scope':'language data orchestration; default stops at real training handoff','external_teacher_configured':False,'holdout_in_training_bundle':False}
  text=canonical(spec);sha=hashlib.sha256(text.encode()).hexdigest();(path/'spec.json').write_text(text+'\n');(path/'spec.sha256').write_text(sha+'\n');now=time.time()
  with self.connect() as c:c.execute('INSERT INTO runs(id,spec,spec_sha,status,created,updated) VALUES(?,?,?,?,?,?)',(rid,text,sha,'NEW',now,now))
  self.event(rid,'created',spec_sha256=sha,config=config.to_dict());return rid
 def get(self,rid):
  safe_id(rid)
  with self.connect() as c:r=c.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
  if r is None:raise KeyError(rid)
  d=dict(r);d['spec']=json.loads(d['spec']);
  with self.connect() as c:completed=c.execute('SELECT COUNT(*) FROM episodes WHERE run_id=?',(rid,)).fetchone()[0]
  d['completed_examples']=completed;d['budget_used_seconds']=d['active_seconds']+d['recovery_charge'];d['remaining_seconds']=max(0,d['spec']['config']['budget_seconds']-d['budget_used_seconds']);d['learning_cycle_complete']=False;d['training_executed']=False
  return d
 def list(self):
  with self.connect() as c:ids=[r[0] for r in c.execute('SELECT id FROM runs ORDER BY created DESC LIMIT 30')]
  return [self.get(i) for i in ids]
 def episodes(self,rid):
  with self.connect() as c:return [json.loads(r[0]) for r in c.execute('SELECT record FROM episodes WHERE run_id=? ORDER BY task_id',(rid,))]
 def record_episode(self,rid,record):
  with self.connect() as c:
   c.execute('BEGIN IMMEDIATE');c.execute('INSERT INTO episodes VALUES(?,?,?)',(rid,record['task_id'],canonical(record)));c.execute('INSERT INTO events(run_id,utc_unix,kind,payload) VALUES(?,?,?,?)',(rid,time.time(),'episode_committed',canonical({'task_id':record['task_id'],'student_pass':record['student_verdict']['pass']})));c.execute('COMMIT')
 def update(self,rid,status=None,error=None):
  with self.connect() as c:
   if status:c.execute('UPDATE runs SET status=?,error=?,updated=? WHERE id=?',(status,error,time.time(),rid))
  if status:self.event(rid,'state',status=status,error=error)
 def control(self,rid,action):
  if action not in ('pause','stop','resume'):raise ValueError(action)
  run=self.get(rid)
  with self.connect() as c:
   c.execute('UPDATE runs SET control=?,updated=? WHERE id=?',('' if action=='resume' else action,time.time(),rid))
   if action=='stop' and not run['owner_pid']:c.execute('UPDATE runs SET status=? WHERE id=?',('STOPPED',rid))
   if action=='pause' and not run['owner_pid'] and run['status']=='NEW':c.execute('UPDATE runs SET status=? WHERE id=?',('PAUSED',rid))
  self.event(rid,'control_requested',action=action)
 def claim(self,rid):
  token=uuid.uuid4().hex;now=time.time()
  with self.connect() as c:
   c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
   if r is None:c.execute('ROLLBACK');raise KeyError(rid)
   alive=False
   if r['owner_pid']:
    try:os.kill(r['owner_pid'],0);alive=True
    except OSError:pass
   if alive and (r['lease_until'] or 0)>now:c.execute('ROLLBACK');raise RuntimeError('This run already has a live worker')
   charge=min(90.,max(0,now-(r['heartbeat'] or now))) if r['owner_pid'] else 0.
   c.execute('UPDATE runs SET owner_pid=?,owner_token=?,lease_until=?,heartbeat=?,recovery_charge=recovery_charge+? WHERE id=?',(os.getpid(),token,now+90,now,charge,rid));c.execute('COMMIT')
  if r['owner_pid']:self.event(rid,'crash_recovery',conservative_budget_charge_seconds=charge,not_a_measured_compute_duration=True)
  return token
 def heartbeat(self,rid,token,active):
  with self.connect() as c:
   q=c.execute('UPDATE runs SET active_seconds=?,heartbeat=?,lease_until=?,updated=? WHERE id=? AND owner_token=?',(active,time.time(),time.time()+90,time.time(),rid,token))
   if q.rowcount!=1:raise RuntimeError('Run lease lost')
 def release(self,rid,token):
  with self.connect() as c:c.execute('UPDATE runs SET owner_pid=NULL,owner_token=NULL,lease_until=NULL WHERE id=? AND owner_token=?',(rid,token))
 def events(self,rid):
  with self.connect() as c:return [dict(r)|{'payload':json.loads(r['payload'])} for r in c.execute('SELECT * FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 100',(rid,))]
