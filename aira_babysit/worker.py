"""Separate, bounded worker. Real LM data collection; never fake a training stage."""
from __future__ import annotations
import fcntl,hashlib,json,os,time,zipfile
from pathlib import Path
import httpx
from .config import RunConfig,canonical,digest,frozen_sources
from .store import Store
from .verification import teacher_record,verify


class Paused(Exception):pass
class Stopped(Exception):pass
class BudgetEnd(Exception):pass
class ResourceBusy(Exception):pass


def check_spec(store,rid):
 r=store.get(rid);path=store.path(rid);spec=json.loads((path/'spec.json').read_text())
 if hashlib.sha256(canonical(spec).encode()).hexdigest()!=r['spec_sha'] or spec!=r['spec']:raise RuntimeError('Immutable run specification changed')
 if frozen_sources()!=spec['sources']:raise RuntimeError('Frozen generator/evaluator source changed; use a new run, not a silent resume')
 for split,sha in spec['pool_sha256'].items():
  if digest(path/f'{split}.jsonl')!=sha:raise RuntimeError('Frozen data pool changed: '+split)
 return r


def collect_student(config,task,checkpoint):
 text='';meta=None;rid=None
 with httpx.Client(base_url=config.student_url.rstrip('/'),timeout=httpx.Timeout(30.,connect=5.)) as client:
  try:
   with client.stream('POST','/api/chat',json={'mode':'model','messages':task['messages'],'max_tokens':config.max_new_tokens,'notes':[]}) as response:
    if response.status_code==429:raise ResourceBusy('Serving model is busy; stopped rather than spin/retry indefinitely')
    response.raise_for_status()
    if 'text/event-stream' not in response.headers.get('content-type',''):raise RuntimeError('Student returned non-SSE data')
    for line in response.iter_lines():
     checkpoint()
     if not line.startswith('data: '):continue
     event=json.loads(line[6:]);kind=event.get('type')
     if kind=='start':rid=event['id']
     elif kind=='token':text+=event['text']
     elif kind=='error':raise RuntimeError(event['message'])
     elif kind=='done':meta=event['metrics']
    if meta is None or meta.get('error'):raise RuntimeError((meta or {}).get('error') or 'Student stream ended without done')
  except BaseException:
   if rid:
    try:client.post('/api/cancel/'+rid,timeout=3.)
    except Exception:pass
   raise
 return {'text':text,'metrics':meta}


def atomic_bytes(path,payload):
 path=Path(path);temp=path.with_name(path.name+'.tmp')
 with temp.open('wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
 temp.replace(path)


def export_bundle(store,rid):
 path=store.path(rid);episodes=store.episodes(rid);spec=store.get(rid)['spec']
 verified=[e for e in episodes if e['teacher']['verified']]
 if not verified:raise RuntimeError('No verified teacher targets: refusing empty training package')
 # Errors are on-policy TRAIN examples, not development/holdout failures.
 chosen=[e for e in verified if not e['student_verdict']['pass'] or int(e['task_id'].split('-')[-1])%5==0]
 if not chosen:chosen=verified[:1]
 out=path/'bundle';out.mkdir(exist_ok=True)
 allowed={'babysit_train.jsonl','teacher_sft_control.jsonl','development.jsonl','run_spec.json','kaggle_train.py','training_data.py','verification.py','manifest.json'}
 if any(p.name not in allowed and not(p.name.endswith('.tmp') and p.name[:-4] in allowed) for p in out.iterdir()):raise RuntimeError('Unexpected bundle files; refuse accidental holdout/secret export')
 def write(name,rows):atomic_bytes(out/name,''.join(canonical(r)+'\n' for r in rows).encode())
 write('babysit_train.jsonl',[e['teacher'] for e in chosen]);write('teacher_sft_control.jsonl',[e['teacher'] for e in verified])
 dev=[json.loads(x) for x in (path/'development.jsonl').read_text().splitlines()]
 write('development.jsonl',dev)
 atomic_bytes(out/'run_spec.json',(canonical(spec)+'\n').encode())
 # Only reviewed source is packaged. No shell commands from the student and no secrets.
 source=Path(__file__).resolve().parent
 for name in ('kaggle_train.py','training_data.py','verification.py'):atomic_bytes(out/name,(source/name).read_bytes())
 manifest={'run_id':rid,'train_records':len(chosen),'plain_sft_control_records':len(verified),'development_records':len(dev),'holdout_included':False,'teacher':'verified_offline, NOT a strong AI teacher','serving_system_prompt':spec['serving_system_prompt'],'student_model_sha256':spec['config']['student_model_sha256'],'training_executed':False,'learning_cycle_complete':False,'budget_used_seconds':store.get(rid)['budget_used_seconds'],'remaining_active_budget_seconds':store.get(rid)['remaining_seconds'],'max_train_steps':spec['config']['max_train_steps'],'files':{name:digest(out/name) for name in sorted(allowed-{'manifest.json'})},'limits':'Synthetic curriculum; files alone do not prove SFT quality. Compare controls at a matched token/compute budget before any superiority claim.'}
 atomic_bytes(out/'manifest.json',(json.dumps(manifest,indent=2)+'\n').encode());zip_path=path/'kaggle_bundle.zip';zip_temp=path/'kaggle_bundle.zip.tmp'
 with zipfile.ZipFile(zip_temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for name in sorted(allowed):z.write(out/name,name)
 zip_temp.replace(zip_path)
 from .notebook import notebook
 notebook_path=path/'kaggle_run.ipynb';atomic_bytes(notebook_path,(json.dumps(notebook(rid,digest(zip_path)),indent=2,ensure_ascii=False)+'\n').encode())
 summary={'notebook_sha256':digest(notebook_path),'run_id':rid,'status':'WAITING_TRAINING','student_calls_committed':len(episodes),'student_passes':sum(e['student_verdict']['pass'] for e in episodes),'student_failures':sum(not e['student_verdict']['pass'] for e in episodes),'train_records':len(chosen),'bundle_sha256':digest(zip_path),'bundle_bytes':zip_path.stat().st_size,'training_executed':False,'learning_cycle_complete':False,'promotion_performed':False,'reason':'Real training backend/checkpoint not available locally. GGUF inference is not SFT.'}
 atomic_bytes(path/'summary.json',(json.dumps(summary,indent=2)+'\n').encode());return summary


def work(store,rid,resume=False,student_fn=collect_student):
 initial=store.get(rid)
 lock_file=(store.root/'worker.lock').open('a')
 try:fcntl.flock(lock_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:
  lock_file.close()
  if not initial['owner_pid']:store.update(rid,'WAITING_RESOURCE','Another autonomous worker is active')
  raise ResourceBusy('Another autonomous worker is active')
 token=None;clock=None;start_active=0.
 try:
  run=check_spec(store,rid)
  if run['status']=='WAITING_TRAINING':return run
  if run['status'] in ('STOPPED','BUDGET_EXHAUSTED'):return run
  if resume:store.control(rid,'resume')
  token=store.claim(rid);clock=time.perf_counter();start_active=run['active_seconds'];config=RunConfig(**run['spec']['config'])
  def checkpoint():
   active=start_active+time.perf_counter()-clock;store.heartbeat(rid,token,active);r=store.get(rid)
   if r['control']=='stop':raise Stopped()
   if r['control']=='pause':raise Paused()
   if r['budget_used_seconds']>=config.budget_seconds:raise BudgetEnd()
  checkpoint()
  if config.teacher=='external_required':
   store.update(rid,'BLOCKED_TEACHER','This chat is not a callable teacher API; configure/verify a teacher before enabling this mode.');return store.get(rid)
  if student_fn is collect_student:
   with httpx.Client(timeout=5) as client:
    status=client.get(config.student_url.rstrip('/')+'/api/status');status.raise_for_status();model=status.json()['model']
    if model['status']!='ready':raise ResourceBusy('Student language model not ready')
    if model.get('sha256')!=config.student_model_sha256:raise RuntimeError('Student model differs from frozen run specification')
  store.update(rid,'COLLECTING');done={e['task_id'] for e in store.episodes(rid)}
  tasks=[json.loads(l) for l in (store.path(rid)/'train.jsonl').read_text().splitlines()]
  for task in tasks:
   check_spec(store,rid);checkpoint()
   if task['id'] in done:continue
   store.event(rid,'student_attempt_start',task_id=task['id'])
   for attempt in range(3):
    try:
     result=student_fn(config,task,checkpoint);break
    except ResourceBusy:
     if attempt==2:raise
     store.event(rid,'resource_backoff',task_id=task['id'],retry=attempt+1,seconds=1.)
     until=time.perf_counter()+1.
     while time.perf_counter()<until:checkpoint();time.sleep(.1)
   checkpoint();verdict=verify(task,result['text']);teacher=teacher_record(task,result['text'])
   teacher['messages']=[{'role':'system','content':run['spec']['serving_system_prompt']}]+teacher['messages']
   record={'task_id':task['id'],'student':result,'student_verdict':verdict,'teacher':teacher,'created_unix':time.time()}
   store.record_episode(rid,record)
   print(canonical({'run_id':rid,'stage':'teacher_verified','task_id':task['id'],'student_pass':verdict['pass'],'committed':True}),flush=True)
   if student_fn is collect_student:
    # Explicit background-resource yield, not fabricated work or speedup.
    until=time.perf_counter()+.2
    while time.perf_counter()<until:checkpoint();time.sleep(.05)
  check_spec(store,rid);checkpoint();store.update(rid,'PACKAGING');summary=export_bundle(store,rid);checkpoint();store.update(rid,'WAITING_TRAINING',summary['reason']);store.event(rid,'training_handoff_ready',**summary)
 except Paused:store.update(rid,'PAUSED')
 except Stopped:store.update(rid,'STOPPED')
 except BudgetEnd:store.update(rid,'BUDGET_EXHAUSTED')
 except ResourceBusy as exc:store.update(rid,'WAITING_RESOURCE',str(exc))
 except KeyboardInterrupt:store.update(rid,'PAUSED','Worker interrupted; committed episodes retained')
 except Exception as exc:store.update(rid,'FAILED',str(exc));raise
 finally:
  try:
   if token:
    try:
     if clock is not None:store.heartbeat(rid,token,start_active+time.perf_counter()-clock)
    finally:store.release(rid,token)
  finally:fcntl.flock(lock_file,fcntl.LOCK_UN);lock_file.close()
 return store.get(rid)
