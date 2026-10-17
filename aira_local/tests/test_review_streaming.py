import asyncio
import json
import queue
import threading
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from aira_local.app import app,state,ChatRequest,_start_chat
from aira_local.jobs import ChatJob
from aira_local import app as module


def payload(text='Посчитай -3+5',mode='calculator'):
 return ChatRequest(messages=[{'role':'user','content':text}],mode=mode,max_tokens=24)


def test_worker_releases_gate_even_if_sse_is_never_consumed():
 job=_start_chat(payload())
 assert job.finished.wait(2)
 assert not state.lock.locked()
 assert job.metrics['error'] is None
 events=[]
 while not job.events.empty():events.append(job.events.get_nowait())
 assert any(e.get('text')=='-3+5 = 2' for e in events)
 assert events[-1]['type']=='done'


def test_backpressure_cancels_instead_of_holding_gate_forever():
 job=ChatJob(queue_size=1);assert job.emit({'type':'start'})
 assert not job.emit({'type':'token','text':'x'})
 assert job.cancel.is_set();assert job.cancel_reason=='slow_client'
 job.complete({'error':'slow client'});assert job.finished.is_set()
 assert job.events.get_nowait()['type']=='done'


def test_job_deadline_is_a_cancellation_reason():
 job=ChatJob(max_seconds=-1)
 assert not job.emit({'type':'start'});assert job.cancel_reason=='timeout'


def test_pending_worker_can_be_cancelled_without_contaminating_next_request(monkeypatch):
 started=threading.Event();release=threading.Event()
 original=state.model
 class ControlledModel:
  status='ready'
  def generate(self,messages,max_tokens,cancel,deadline=None):
   started.set()
   while not cancel.wait(.01):
    if release.is_set():break
   yield {'type':'model_end','generated_tokens':0,'cancelled':cancel.is_set(),'text':''}
  def clear_context(self):release.set()
 with monkeypatch.context() as patch:
  patch.setattr(state,'model',ControlledModel())
  job=_start_chat(payload('hello','model'));assert started.wait(1)
  job.request_cancel('disconnect');assert job.finished.wait(2)
  assert not state.busy();assert state.active_job is None
 assert state.model is original
 next_job=_start_chat(payload());assert next_job.finished.wait(2);assert next_job.metrics['error'] is None


def test_headers_health_and_optional_pilot_do_not_break_chat(monkeypatch):
 with TestClient(app) as client:
  for path in ('/','/static/app.js','/static/transport.js','/api/status','/api/health'):
   r=client.get(path);assert r.status_code==200;assert r.headers['cache-control']=='no-store';assert r.headers['x-aira-version']=='0.2.0'
  with monkeypatch.context() as patch:
   patch.setattr(module,'PILOT_REPORT',None);patch.setattr(state,'router',None)
   s=client.get('/api/status');assert s.status_code==200;assert s.json()['router']['available'] is False
   r=client.post('/api/chat',json=payload().model_dump());assert r.status_code==200;assert '-3+5 = 2' in r.text
   assert client.get('/api/lab').status_code==503


def test_active_cancel_id_not_published_and_completed_cancel_is_idempotent():
 job=_start_chat(payload());assert job.finished.wait(2)
 with TestClient(app) as c:
  assert c.get('/api/status').json()['active_id'] is None
  r=c.post('/api/cancel/'+job.id);assert r.status_code==200;assert r.json()['already_finished']


def test_telemetry_can_restart_after_lifespan():
 t=state.telemetry;t.start();first=t.thread;t.stop.set();first.join(1);t.start()
 assert t.thread.is_alive();t.stop.set();t.thread.join(1)


def test_corrupt_optional_json_is_not_a_status_dependency(tmp_path):
 p=tmp_path/'bad.json';p.write_text('{broken');assert module.optional_json(p) is None
 p.write_text('[1,2,3]');assert module.optional_json(p) is None
 assert module.optional_json(tmp_path/'missing') is None


def test_thread_launch_failure_does_not_leave_a_busy_server(monkeypatch):
 def failed(self):raise RuntimeError('simulated thread resource failure')
 with monkeypatch.context() as patch:
  patch.setattr(threading.Thread,'start',failed)
  with pytest.raises(RuntimeError):_start_chat(payload())
 assert not state.busy();assert state.active_job is None


def test_cleanup_failure_still_releases_gate(monkeypatch):
 class BadCleanup:
  status='ready'
  def generate(self,*args,**kwargs):
   yield {'type':'model_end','generated_tokens':0,'text':''}
  def clear_context(self):raise RuntimeError('simulated cleanup failure')
 with monkeypatch.context() as patch:
  patch.setattr(state,'model',BadCleanup());job=_start_chat(payload('hello','model'))
  assert job.finished.wait(2);assert job.metrics['error'];assert not state.busy()


def test_real_model_context_overflow_is_error_not_a_stuck_job():
 state.model.load();job=_start_chat(payload('жщюя'*500,'model'))
 assert job.finished.wait(5);assert job.metrics['error'];assert job.metrics['generated_tokens']==0
 assert not state.busy();assert state.model.model.n_tokens==0
