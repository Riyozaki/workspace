import json
import pytest
from fastapi.testclient import TestClient
from aira_local.app import app,state


@pytest.fixture(scope='module')
def client():
 state.model.load()
 with TestClient(app) as c:yield c


def events(response):return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


def test_static_and_status(client):
 assert client.get('/').status_code==200;assert client.get('/static/app.js').status_code==200
 s=client.get('/api/status').json();assert s['model']['status']=='ready';assert s['model']['gpu_layers']==0;assert s['model']['threads']==1;assert s['telemetry']['energy_joules'] is None
 assert s['router']['pilot_status'].startswith('failed')


def test_full_calculator_stream_and_explicit_attribution(client):
 r=client.post('/api/chat',json={'messages':[{'role':'user','content':'Посчитай (18+7)*4'}],'mode':'calculator'})
 assert r.status_code==200;out=events(r);assert out[0]['used']=='calculator';assert any(e.get('value')==100 for e in out);assert out[-1]['type']=='done';assert out[-1]['metrics']['generated_tokens']==0


def test_local_notes_only(client):
 r=client.post('/api/chat',json={'messages':[{'role':'user','content':'Найди в заметках план обучения'}],'mode':'notes','notes':[{'id':'one','title':'План обучения','text':'Большое обучение позже на Kaggle.'}]})
 out=events(r);assert out[0]['used']=='notes';assert any('Kaggle' in e.get('text','') for e in out)


def test_real_model_tokens_not_a_canned_reply(client):
 r=client.post('/api/chat',json={'messages':[{'role':'user','content':'Explain what RAM does briefly.'}],'mode':'model','max_tokens':24})
 out=events(r);assert out[0]['used']=='model';assert out[-1]['metrics']['generated_tokens']>0;assert any(e['type']=='token' for e in out);assert out[-1]['metrics']['model_metrics']['prompt_tokens']>0
 assert 'text' not in client.get('/api/status').json()['last_request']['model_metrics']
 assert state.model.model.n_tokens==0


def test_limits_busy_and_no_implicit_training(client):
 assert client.post('/api/lab/predict',content=b'x'*140000).status_code==413
 assert client.post('/api/chat',json={'messages':[]}).status_code==422
 assert client.post('/api/chat',json={'messages':[{'role':'user','content':'hello'}],'max_tokens':100000}).status_code==422
 assert client.post('/api/cancel/not-a-request').status_code==404
 state.lock.acquire()
 try:assert client.post('/api/chat',json={'messages':[{'role':'user','content':'hello'}]}).status_code==429
 finally:state.lock.release()
 assert client.get('/api/lab').json()['feedback']==[]


def test_teacher_correction_is_explicit_and_lm_weights_unchanged(client):
 assert client.post('/api/lab/train',json={}).status_code==400
 r=client.post('/api/lab/feedback',json={'prompt':'Сосчитай пожалуйста: 28 + 14','target':'calculator','why':'Явное арифметическое выражение.'});assert r.status_code==200;assert not r.json()['language_model_weights_changed']
 assert client.get('/api/lab').json()['feedback'][0]['target']=='calculator'
 assert client.get('/api/lab/export').status_code==200
