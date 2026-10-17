"""Local control plane. No model-controlled commands, credentials or external URLs."""
from __future__ import annotations
import json,os,subprocess,sys,threading
from pathlib import Path
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from .config import DEFAULT_RUNS,ROOT,RunConfig,safe_id
from .store import Store
from aira_local.middleware import BodyLimitMiddleware,NoStoreHeaders

store=Store(os.environ.get('AIRA_RUNS_ROOT',str(DEFAULT_RUNS)));app=FastAPI(title='AI Babysit — Auto Runs');app.add_middleware(BodyLimitMiddleware,max_bytes=8192);app.add_middleware(NoStoreHeaders,version='autopilot-0.1');processes={};launch_lock=threading.Lock()


class Request(BaseModel):
 budget_seconds:int=Field(default=3600,ge=30,le=7200)
 max_examples:int=Field(default=12,ge=1,le=128)
 teacher:str='verified_offline'


def public(r):
 r=dict(r);proc=processes.get(r['id']);alive=False
 if r.get('owner_pid') and (r.get('lease_until') or 0)>__import__('time').time():
  try:os.kill(r['owner_pid'],0);alive=True
  except OSError:pass
 r['worker_running']=alive or bool(proc is not None and proc.poll() is None);r.pop('owner_token',None);r.pop('owner_pid',None);r['bundle_ready']=(store.path(r['id'])/'summary.json').exists();r['notebook_ready']=r['bundle_ready'] and (store.path(r['id'])/'kaggle_run.ipynb').exists();return r

def get(rid):
 try:return store.get(rid)
 except (KeyError,ValueError):raise HTTPException(404,'Запуск не найден')

def launch(rid,resume=False):
 if any(p.poll() is None for p in processes.values()):raise HTTPException(429,'Один worker уже работает. Сначала pause/stop.')
 logfile=store.path(rid)/'worker.log'
 with logfile.open('a') as f:
  processes[rid]=subprocess.Popen([sys.executable,'-m','aira_babysit','--runs-root',str(store.root),'resume' if resume else 'work',rid],cwd=ROOT.parent,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)


@app.get('/')
def index():return FileResponse(ROOT/'static/index.html',headers={'Cache-Control':'no-store'})


@app.get('/api/runs')
def runs():return {'runs':[public(r) for r in store.list()],'teacher_mode':'verified_offline synthetic only','real_gpu_training_available_here':False}


@app.post('/api/runs')
def create(req:Request):
 if req.teacher!='verified_offline':raise HTTPException(422,'В UI разрешён только проверяемый офлайн-учитель; внешний AI teacher не настроен.')
 with launch_lock:
  if any(p.poll() is None for p in processes.values()) or any(public(r)['worker_running'] for r in store.list()):raise HTTPException(429,'Worker уже запущен')
  manifest=json.loads((ROOT.parent/'aira_local/model_manifest.json').read_text())
  cfg=RunConfig(budget_seconds=req.budget_seconds,max_examples=req.max_examples,student_model_sha256=manifest['gguf_sha256'])
  rid=store.create(cfg);launch(rid);return public(store.get(rid))


@app.get('/api/runs/{rid}')
def details(rid:str):return {'run':public(get(rid)),'events':store.events(rid)}


@app.post('/api/runs/{rid}/{action}')
def control(rid:str,action:str):
 run=get(rid)
 if action not in ('pause','stop','resume'):raise HTTPException(404,'Unknown action')
 with launch_lock:
  if action=='resume':
   if run['status'] in ('WAITING_TRAINING','STOPPED','BUDGET_EXHAUSTED'):raise HTTPException(409,'Этот запуск не ждёт возобновления сбора. Обучение нельзя заменить повторным сбором.')
   launch(rid,True)
  else:store.control(rid,action)
 return public(store.get(rid))


@app.get('/api/runs/{rid}/bundle/download')
def bundle(rid:str):
 get(rid);p=store.path(rid)/'kaggle_bundle.zip'
 if not p.exists():raise HTTPException(404,'Пакет ещё не создан')
 return FileResponse(p,media_type='application/zip',filename=f'aira-babysit-{rid}.zip')


@app.get('/api/runs/{rid}/notebook/download')
def download_notebook(rid:str):
 get(rid);p=store.path(rid)/'kaggle_run.ipynb'
 if not p.exists():raise HTTPException(404,'Notebook ещё не создан для этого run')
 return FileResponse(p,media_type='application/x-ipynb+json',filename=f'aira-babysit-{rid}.ipynb')
