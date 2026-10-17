import json,sqlite3,subprocess,sys,threading,time,zipfile
from pathlib import Path
import pytest
from aira_babysit.config import RunConfig
from aira_babysit.store import Store
from aira_babysit.tasks import make_tasks
from aira_babysit.verification import verify,teacher_record
from aira_babysit.worker import work,ResourceBusy
from aira_babysit.kaggle_train import validate_bundle


def make(tmp_path,n=6,teacher='verified_offline'):
 store=Store(tmp_path);rid=store.create(RunConfig(max_examples=n,teacher=teacher,student_model_sha256='f'*64))
 return store,rid


def fake_student(config,task,checkpoint):
 # Explicit unit fixture, NOT a model or successful training claim.
 checkpoint();return {'text':'wrong fixture output','metrics':{'generated_tokens':3}}


def test_full_local_phase_stops_honestly_at_training_handoff(tmp_path):
 store,rid=make(tmp_path);r=work(store,rid,student_fn=fake_student)
 assert r['status']=='WAITING_TRAINING';assert r['completed_examples']==6;assert not r['training_executed'];assert not r['learning_cycle_complete'];assert r['owner_pid'] is None
 bundle=store.path(rid)/'bundle';manifest,train,dev=validate_bundle(bundle)
 assert manifest['holdout_included'] is False
 with zipfile.ZipFile(store.path(rid)/'kaggle_bundle.zip') as z:assert not any('holdout' in n for n in z.namelist())
 assert not {r['family'] for r in train}&{r['family'] for r in dev}
 assert all(teacher_record(t,'wrong')['verified'] for t in make_tasks(20,2,'train'))
 count=len(store.episodes(rid));work(store,rid,student_fn=lambda *a:pytest.fail('waiting run must not recollect'));assert len(store.episodes(rid))==count


def test_pause_resume_does_not_duplicate_committed_episodes(tmp_path):
 store,rid=make(tmp_path);calls=[]
 def student(config,task,checkpoint):
  calls.append(task['id'])
  if len(calls)==2:store.control(rid,'pause');checkpoint()
  return fake_student(config,task,checkpoint)
 assert work(store,rid,student_fn=student)['status']=='PAUSED';assert len(store.episodes(rid))==1
 result=work(store,rid,resume=True,student_fn=fake_student)
 ids=[r['task_id'] for r in store.episodes(rid)];assert len(ids)==len(set(ids))==6;assert result['status']=='WAITING_TRAINING'


def test_stop_new_run_performs_no_student_call(tmp_path):
 store,rid=make(tmp_path);store.control(rid,'stop')
 assert work(store,rid,student_fn=lambda *a:pytest.fail('stopped run executed'))['status']=='STOPPED'


def test_budget_is_cumulative_and_not_faked(tmp_path):
 store,rid=make(tmp_path)
 with store.connect() as c:c.execute('UPDATE runs SET active_seconds=3599.99 WHERE id=?',(rid,))
 def student(config,task,checkpoint):time.sleep(.03);checkpoint()
 result=work(store,rid,student_fn=student);assert result['status']=='BUDGET_EXHAUSTED';assert result['active_seconds']>=3600;assert not store.episodes(rid)


def test_missing_external_teacher_blocks_before_inference(tmp_path):
 store,rid=make(tmp_path,teacher='external_required')
 result=work(store,rid,student_fn=lambda *a:pytest.fail('no teacher should mean no inference charge'))
 assert result['status']=='BLOCKED_TEACHER';assert result['completed_examples']==0


def test_data_or_spec_tampering_cannot_resume_as_if_valid(tmp_path):
 store,rid=make(tmp_path);(store.path(rid)/'train.jsonl').write_text('{}\n')
 with pytest.raises(RuntimeError,match='data pool'):work(store,rid,student_fn=fake_student)
 assert store.get(rid)['status']=='FAILED'


def test_live_lease_and_global_worker_lock(tmp_path):
 store,rid=make(tmp_path);token=store.claim(rid)
 with pytest.raises(RuntimeError,match='live worker'):store.claim(rid)
 store.release(rid,token)
 started=threading.Event();release=threading.Event();fail=[]
 def blocked(config,task,checkpoint):started.set();release.wait(2);return fake_student(config,task,checkpoint)
 def target():
  try:work(store,rid,student_fn=blocked)
  except Exception as e:fail.append(e)
 t=threading.Thread(target=target);t.start();assert started.wait(1)
 other=store.create(RunConfig(max_examples=1,student_model_sha256='f'*64))
 with pytest.raises(ResourceBusy):work(store,other,student_fn=fake_student)
 assert store.get(rid)['status']=='COLLECTING';assert store.get(other)['status']=='WAITING_RESOURCE'
 release.set();t.join(5);assert not t.is_alive();assert not fail


def test_crash_recovery_budget_charge_is_labeled_not_a_measurement(tmp_path):
 store,rid=make(tmp_path)
 with store.connect() as c:c.execute('UPDATE runs SET owner_pid=99999999,heartbeat=?,lease_until=? WHERE id=?',(time.time()-20,time.time()-1,rid))
 result=work(store,rid,student_fn=fake_student);assert result['recovery_charge']>=20
 event=next(e for e in store.events(rid) if e['kind']=='crash_recovery');assert event['payload']['not_a_measured_compute_duration']


def test_student_text_is_never_interpreted_as_policy_or_code():
 for task in make_tasks(20,1,'train'):
  assert not verify(task,'ignore all checks; import os')['pass']
  assert verify(task,task['teacher_target'])['pass']


def test_packaged_check_runs_without_torch_and_never_claims_training(tmp_path):
 store,rid=make(tmp_path);work(store,rid,student_fn=fake_student);p=store.path(rid)/'bundle'
 r=subprocess.run([sys.executable,str(p/'kaggle_train.py'),'--bundle',str(p),'--check-bundle'],capture_output=True,text=True)
 assert r.returncode==0,r.stderr;d=json.loads(r.stdout);assert d['bundle_valid'];assert not d['training_executed'];assert not d['gpu_run_verified']


def test_notebook_has_exact_bundle_hash_and_no_executed_outputs(tmp_path):
 store,rid=make(tmp_path);work(store,rid,student_fn=fake_student);path=store.path(rid)
 nb=json.loads((path/'kaggle_run.ipynb').read_text());summary=json.loads((path/'summary.json').read_text())
 assert nb['metadata']['aira']['bundle_sha256']==summary['bundle_sha256']
 assert nb['metadata']['aira']['training_executed_in_sandbox'] is False
 for cell in nb['cells']:
  if cell['cell_type']=='code':assert cell['execution_count'] is None;assert cell['outputs']==[];compile(''.join(cell['source']),'notebook','exec')


def test_unexpected_bundle_file_cannot_leak_into_export(tmp_path):
 store,rid=make(tmp_path);out=store.path(rid)/'bundle';out.mkdir();(out/'holdout.jsonl').write_text('secret test targets')
 with pytest.raises(RuntimeError,match='Unexpected'):work(store,rid,student_fn=fake_student)
 assert not (store.path(rid)/'kaggle_bundle.zip').exists()


def test_real_training_cannot_succeed_without_a_training_backend(tmp_path):
 store,rid=make(tmp_path);work(store,rid,student_fn=fake_student);p=store.path(rid)/'bundle'
 r=subprocess.run([sys.executable,'-S',str(p/'kaggle_train.py'),'--bundle',str(p),'--base-model','approved/model','--base-revision','f'*40],capture_output=True,text=True)
 assert r.returncode!=0;assert 'Training NOT executed' in r.stderr
 assert not (tmp_path/'training_receipt.json').exists()


@pytest.mark.parametrize('url',['http://localhost:8000@evil.example','http://127.0.0.1:8000/redirect','https://localhost:8000','http://example.com:8000','http://localhost:bad'])
def test_student_endpoint_cannot_escape_approved_loopback(url):
 with pytest.raises(ValueError):RunConfig(student_url=url,student_model_sha256='f'*64).validate()
