from fastapi.testclient import TestClient
from aira_babysit import dashboard
from aira_babysit.store import Store


def test_dashboard_controls_have_bounded_inputs_and_no_arbitrary_commands(tmp_path,monkeypatch):
 monkeypatch.setattr(dashboard,'store',Store(tmp_path));monkeypatch.setattr(dashboard,'processes',{})
 launches=[]
 monkeypatch.setattr(dashboard,'launch',lambda rid,resume=False:launches.append((rid,resume)))
 with TestClient(dashboard.app) as c:
  assert c.get('/').status_code==200
  assert c.get('/api/runs').headers['cache-control']=='no-store'
  assert c.post('/api/runs',json={'teacher':'external_required'}).status_code==422
  assert c.post('/api/runs',json={'max_examples':1000}).status_code==422
  assert c.post('/api/runs',json={'budget_seconds':999999}).status_code==422
  assert c.post('/api/runs',content=b'x'*9000).status_code==413
  r=c.post('/api/runs',json={'max_examples':2});assert r.status_code==200
  data=r.json();rid=data['id'];assert 'owner_token' not in data;assert 'owner_pid' not in data;assert data['training_executed'] is False
  assert launches==[(rid,False)]
  assert c.post(f'/api/runs/{rid}/pause',json={}).json()['status']=='PAUSED'
  assert c.post(f'/api/runs/{rid}/resume',json={}).status_code==200;assert launches[-1]==(rid,True)
  assert c.get(f'/api/runs/{rid}/bundle/download').status_code==404
  assert c.get(f'/api/runs/{rid}/notebook/download').status_code==404
  assert c.post(f'/api/runs/{rid}/exec',json={}).status_code==404
  assert c.get('/api/runs/not-a-safe-id').status_code==404
  assert c.post(f'/api/runs/{rid}/stop',json={}).json()['status']=='STOPPED'
  assert c.post(f'/api/runs/{rid}/resume',json={}).status_code==409
