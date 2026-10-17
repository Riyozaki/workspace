"""AIra Local Lab. A real local LM + explicitly separated tool/router pilot."""
from __future__ import annotations
import asyncio,json,os,queue,threading,time,uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import psutil
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .engine import LocalLanguageModel
from .router import BudgetRouter,ROOT,metrics,calibrate
from .train_router import load_data
from .tools import calculate,extract_expression,search_notes,CalculatorError
from .guard import non_regression
from .jobs import ChatJob

ART=ROOT.parent/'artifacts/aira_local';ART.mkdir(parents=True,exist_ok=True)
def optional_json(path):
 try:
  result=json.loads(Path(path).read_text());return result if isinstance(result,dict) else None
 except (OSError,ValueError):return None
MODEL_MANIFEST=optional_json(ROOT/'model_manifest.json') or {}
PILOT_REPORT=optional_json(ROOT/'results/router_ablation.json')


class Telemetry:
 def __init__(self):
  self.process=psutil.Process();self.cpus=len(os.sched_getaffinity(0));self.points=deque(maxlen=90);self.peak_rss=0;self.stop=threading.Event();self.thread=None;self.cpu_percent=0.
 def start(self):
  if self.thread and self.thread.is_alive():return
  self.stop.clear()
  def sample():
   prev=self.process.cpu_times();t0=time.perf_counter()
   while not self.stop.wait(.65):
    now=time.perf_counter();c=self.process.cpu_times();rss=self.process.memory_info().rss
    cpu=max(0.,100*((c.user+c.system)-(prev.user+prev.system))/max(now-t0,1e-6)/self.cpus);self.cpu_percent=min(100.,cpu);self.peak_rss=max(self.peak_rss,rss)
    self.points.append({'t':time.time(),'cpu_percent_total_capacity':self.cpu_percent,'rss_bytes':rss});prev=c;t0=now
  self.thread=threading.Thread(target=sample,daemon=True);self.thread.start()
 def snapshot(self):
  mem=psutil.virtual_memory()
  return {'rss_bytes':self.process.memory_info().rss,'peak_sampled_rss_bytes':self.peak_rss,'cpu_percent_total_capacity':self.cpu_percent,'logical_cpu_limit':self.cpus,'native_inference_threads':1,'os_threads':self.process.num_threads(),'system_memory_bytes':mem.total,'available_memory_bytes':mem.available,'energy_joules':None,'power_watts':None,'energy_status':'not measured: no calibrated energy sensor','history':list(self.points)}


class State:
 def __init__(self):
  self.model=LocalLanguageModel();self.router=None;self.router_error=None
  try:self.router=BudgetRouter.load(ROOT/'models/budget_router.json')
  except Exception as exc:self.router_error=str(exc)
  self.telemetry=Telemetry();self.lock=threading.Lock();self.feedback_lock=threading.Lock()
  self.active_job=None;self.active_kind=None;self.completed_ids=deque(maxlen=16);self.last=None;self.feedback=[]
  self.training={'status':'idle'};self.router_is_published=True;self.training_attempts=0
 @property
 def active_id(self):return self.active_job.id if self.active_job else None
 def busy(self):return self.lock.locked()

state=State()


@asynccontextmanager
async def lifespan(app):
 state.telemetry.start()
 async def load():
  try:await asyncio.to_thread(state.model.load)
  except Exception:pass
 task=asyncio.create_task(load())
 yield
 if state.active_job:
  job=state.active_job;job.request_cancel('shutdown')
  if job.thread:await asyncio.to_thread(job.thread.join,5.)
 state.telemetry.stop.set()
 if state.telemetry.thread:await asyncio.to_thread(state.telemetry.thread.join,1.)
 if not task.done():task.cancel()

APP_VERSION='0.2.0'
app=FastAPI(title='AIra Local Lab',version=APP_VERSION,lifespan=lifespan)
from .middleware import BodyLimitMiddleware,NoStoreHeaders
app.add_middleware(BodyLimitMiddleware,max_bytes=131072)
app.add_middleware(NoStoreHeaders,version=APP_VERSION)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')


class Message(BaseModel):
 role:Literal['user','assistant']
 content:str=Field(min_length=1,max_length=4000)
class Note(BaseModel):
 id:str=Field(default='note',max_length=60)
 title:str=Field(default='Заметка',max_length=120)
 text:str=Field(default='',max_length=6000)
class ChatRequest(BaseModel):
 messages:list[Message]=Field(min_length=1,max_length=8)
 mode:Literal['model','auto','calculator','notes']='model'
 max_tokens:int=Field(default=96,ge=8,le=160)
 notes:list[Note]=Field(default_factory=list,max_length=8)
class PredictionRequest(BaseModel):
 text:str=Field(min_length=1,max_length=700)
class Correction(BaseModel):
 prompt:str=Field(min_length=2,max_length=500)
 target:Literal['chat','calculator','notes']
 why:str=Field(min_length=3,max_length=1000)


def event(data):return 'data: '+json.dumps(data,ensure_ascii=False)+'\n\n'


@app.get('/')
def index():return FileResponse(ROOT/'static/index.html',headers={'Cache-Control':'no-store'})


@app.get('/api/health')
def health():return {'ok':True,'version':APP_VERSION,'model_status':state.model.status}


@app.get('/api/status')
def status():
 pilot=PILOT_REPORT or {}
 return {'app':'AIra Local Lab','version':APP_VERSION,'prototype':True,
 'model':{'status':state.model.status,'error':state.model.error,'id':'SmolLM2-135M-Instruct','nominal_parameters':135000000,'quantization':'Q4_1','file_bytes':MODEL_MANIFEST.get('gguf_bytes'),'sha256':MODEL_MANIFEST.get('gguf_sha256'),'context':1024,'threads':1,'gpu_layers':0,'load_seconds':state.model.load_seconds,'runtime_system_info':state.model.system_info,'trained_here':False,'russian_validated':False},
 'router':{'kind':state.router.kind if state.router else None,'parameters':state.router.parameters if state.router else 0,'threshold':state.router.threshold if state.router else None,'available':state.router is not None,'error':state.router_error,'published_version':state.router_is_published,'scope':'intent classifier, NOT a language model','pilot_holdout':pilot.get('deployed_holdout'),'pilot_status':'failed to generalize; automatic routing is experimental, not default' if pilot else 'pilot report unavailable'},
 'telemetry':state.telemetry.snapshot(),'busy':state.busy(),'active_id':None,'active_kind':state.active_kind,
 'last_request':state.last,'training':state.training,'privacy':'No third-party model API. Inference runs in the Arena backend, not in your browser. No chat-content logging or automatic training on conversations.'}


@app.post('/api/model/retry')
def retry_model():
 if state.model.status=='ready':return {'status':'ready'}
 if not state.lock.acquire(blocking=False):raise HTTPException(429,'Сначала завершите текущую операцию')
 state.active_kind='model_loading'
 def load():
  try:state.model.load()
  except Exception:pass
  finally:state.active_kind=None;state.lock.release()
 try:threading.Thread(target=load,daemon=True).start()
 except Exception:state.active_kind=None;state.lock.release();raise
 return {'status':'loading'}


def _chat_worker(job,req):
 generated=0;ttfc=None;route=None;used=req.mode;model_metrics={};error=None;cpu0=None
 try:
  cpu0=state.telemetry.process.cpu_times()
  if req.mode=='auto':
   try:
    if state.router is None:raise RuntimeError(state.router_error or 'Router unavailable')
    route=state.router.route(req.messages[-1].content)
   except Exception as exc:route={'selected':'chat','accepted_fast_path':False,'error':str(exc),'kind':None,'parameters':0}
   used=route['selected'] if route.get('accepted_fast_path') else 'model'
  job.emit({'type':'start','id':job.id,'used':used,'route':route,'automatic_routing_experimental':req.mode=='auto'})
  text=req.messages[-1].content
  if job.cancel.is_set():return
  if used=='calculator':
   expression=extract_expression(text);value=calculate(expression)
   job.emit({'type':'tool','tool':'calculator','source':value['source'],'expression':expression,'value':value['value']})
   ttfc=time.perf_counter()-job.started;job.emit({'type':'token','text':f"{value['expression']} = {value['text']}"})
  elif used=='notes':
   matches=search_notes(text,[n.model_dump() for n in req.notes])
   job.emit({'type':'tool','tool':'notes','matches':matches,'source':'lexical local retrieval; not a language-model answer'})
   answer='\n\n'.join(f"[{m['title']}]\n{m['text']}" for m in matches) if matches else 'В переданных заметках совпадений не найдено. Я не искал на диске и не использовал интернет.'
   ttfc=time.perf_counter()-job.started;job.emit({'type':'token','text':answer})
  else:
   if state.model.status!='ready':raise RuntimeError('Языковая модель ещё не готова. Инструменты доступны отдельно.')
   for e in state.model.generate([m.model_dump() for m in req.messages],req.max_tokens,job.cancel,deadline=job.deadline):
    if e['type']=='token':
     generated=e.get('generated_tokens',generated)
     if ttfc is None:ttfc=time.perf_counter()-job.started
     job.emit(e)
    elif e['type']=='model_end':
     model_metrics={k:v for k,v in e.items() if k not in ('text','type')};generated=e['generated_tokens']
    else:job.emit(e)
 except Exception as exc:
  error=str(exc);job.emit({'type':'error','message':error})
 finally:
  # The producer owns cleanup and gate release. Never depend on whether a
  # browser starts reading, remains connected, or ever consumes the SSE body.
  try:
   if used=='model':state.model.clear_context()
   if time.perf_counter()>=job.deadline:job.request_cancel('timeout')
   if job.cancel_reason=='timeout':error=error or 'Превышен срок выполнения запроса.'
   if job.cancel_reason=='slow_client':error=error or 'Получатель слишком долго не читает ответ.'
   elapsed=time.perf_counter()-job.started;cpu1=state.telemetry.process.cpu_times()
   cpu=(cpu1.user+cpu1.system)-(cpu0.user+cpu0.system) if cpu0 else 0.
   metrics={'id':job.id,'mode':req.mode,'used':used,'request_seconds':elapsed,'server_first_content_seconds':ttfc,'generated_tokens':generated,'cpu_seconds_process':cpu,'cpu_percent_total_capacity_average':100*cpu/max(elapsed,1e-6)/state.telemetry.cpus if elapsed>=.1 else None,'rss_bytes_at_end':state.telemetry.process.memory_info().rss,'energy_joules':None,'model_metrics':model_metrics,'cancelled':job.cancel.is_set(),'cancel_reason':job.cancel_reason,'error':error,'answer_content_stored':False}
  except Exception as exc:
   metrics={'id':job.id,'mode':req.mode,'used':used,'request_seconds':time.perf_counter()-job.started,'generated_tokens':generated,'server_first_content_seconds':ttfc,'energy_joules':None,'model_metrics':{},'cancelled':True,'error':'Не удалось завершить очистку: '+str(exc),'answer_content_stored':False}
  finally:
   if state.active_job is job:state.active_job=None;state.active_kind=None
   state.completed_ids.append(job.id)
   state.last=metrics
   state.lock.release()
   job.complete(metrics)


def _start_chat(req):
 if not state.lock.acquire(blocking=False):raise HTTPException(429,'Сервер занят другой операцией. Черновик сохранён; повторите через несколько секунд.')
 job=ChatJob();state.active_job=job;state.active_kind='chat'
 try:
  job.thread=threading.Thread(target=_chat_worker,args=(job,req),daemon=True,name='aira-generation')
  job.thread.start()
 except BaseException:
  state.active_job=None;state.active_kind=None;state.lock.release();raise
 return job


@app.post('/api/chat')
async def chat(req:ChatRequest):
 if req.messages[-1].role!='user':raise HTTPException(422,'Last message must be from user')
 if req.mode=='model' and state.model.status!='ready':raise HTTPException(503,'Модель загружается или недоступна. Инструменты можно использовать отдельно.')
 job=_start_chat(req)
 async def stream():
  try:
   while True:
    try:e=await asyncio.to_thread(job.events.get,True,.5)
    except queue.Empty:
     if job.finished.is_set():break
     yield ': heartbeat\n\n';continue
    yield event(e)
    if e['type']=='done':break
  finally:
   if not job.finished.is_set():job.request_cancel('disconnect')
 return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})


@app.post('/api/cancel/{rid}')
def cancel(rid:str):
 job=state.active_job
 if job is not None and job.id==rid:
  job.request_cancel('user');return {'cancel_requested':True}
 if rid in state.completed_ids:return {'cancel_requested':False,'already_finished':True}
 raise HTTPException(404,'Операция не найдена или уже удалена из короткого журнала')


@app.get('/api/lab')
def lab():
 report=PILOT_REPORT
 if report is None:raise HTTPException(503,'Архив пилота недоступен; обычный диалог и инструменты продолжают работать.')
 try:rows=load_data()
 except (OSError,ValueError):raise HTTPException(503,'Учебные данные недоступны; обычный диалог работает.')
 return {'report':report,'train_examples':[r for r in rows if r['split']=='train'][:8],'feedback':state.feedback,'training':state.training,'live_router_published':state.router_is_published,'limits':['This pilot trains only the intent router, not SmolLM2.','Pilot holdout generalization failed; no new-architecture or frontier-quality claim.','Feedback examples are training data; live retraining reports development only.']}


@app.post('/api/lab/predict')
def lab_predict(req:PredictionRequest):
 if state.router is None:raise HTTPException(503,'Роутер недоступен')
 return state.router.route(req.text)


@app.post('/api/lab/feedback')
def feedback(req:Correction):
 if state.router is None:raise HTTPException(503,'Роутер недоступен')
 record=req.model_dump();record['student_before']=state.router.route(req.prompt);record['source']='explicit user teacher correction'
 with state.feedback_lock:
  if len(state.feedback)>=30:raise HTTPException(400,'Достигнут лимит 30 исправлений за сессию')
  state.feedback.append(record)
 return {'added':True,'count':len(state.feedback),'record':record,'language_model_weights_changed':False}


@app.post('/api/lab/train')
def train():
 if state.router is None:raise HTTPException(503,'Роутер недоступен')
 if not state.feedback:raise HTTPException(400,'Сначала добавьте хотя бы одно исправление учителя')
 if not state.lock.acquire(blocking=False):raise HTTPException(429,'Сначала завершите текущую операцию')
 if state.training_attempts>=10:
  state.lock.release();raise HTTPException(429,'Лимит 10 учебных запусков в этой демонстрационной сессии')
 state.training_attempts+=1;state.active_kind='training'
 job_id=uuid.uuid4().hex;started=time.time()
 state.training={'status':'running','started_unix':started,'job_id':job_id}
 with state.feedback_lock:records=[dict(r) for r in state.feedback]
 def work():
  try:
   data=load_data();base=[r for r in data if r['split']=='train'];dev=[r for r in data if r['split']=='development'];teacher=[{'prompt':r['prompt'],'target':r['target']} for r in records]
   before_development=metrics(state.router,dev)
   student=BudgetRouter(state.router.kind,state.router.seed,state.router.threshold,{k:v.copy() for k,v in state.router.p.items()});train_rows=base+teacher*3
   result=student.fit([r['prompt'] for r in train_rows],[r['target'] for r in train_rows],steps=180,lr=.004);development=calibrate(student,dev)
   promoted=non_regression(before_development,development)
   after=[{'prompt':r['prompt'],'expected':r['target'],'before':r['student_before'],'after':student.route(r['prompt'])} for r in records]
   student.save(ART/'router_candidate.json',{'scope':'interactive feedback candidate; no new independent test','feedback_n':len(records),'promoted':promoted})
   if promoted:
    student.save(ART/'live_router.json',{'scope':'development-gated live router, NOT independently tested','feedback_n':len(records)})
    state.router=student;state.router_is_published=False
   state.training={'status':'done','job_id':job_id,'started_unix':started,'fit':result,'before_development':before_development,'development':development,'promoted':promoted,'promotion_reason':'development non-regression gate passed' if promoted else 'development regression: previous router retained','feedback_results':after,'language_model_weights_changed':False,'independent_holdout_evaluated':False}
  except Exception as exc:state.training={'status':'error','job_id':job_id,'error':str(exc)}
  finally:state.active_kind=None;state.lock.release()
 try:threading.Thread(target=work,daemon=True).start()
 except Exception:
  state.training={'status':'error','job_id':job_id,'error':'Не удалось запустить поток обучения'};state.active_kind=None;state.lock.release();raise
 return {'started':True,'job_id':job_id,'scope':'router only; development metrics only; previous published holdout is NOT a score for the new weights'}


@app.get('/api/lab/export')
def export():
 source=ROOT/'data/babysit_seed.jsonl'
 if not source.exists():raise HTTPException(404,'Seed dataset unavailable')
 return FileResponse(source,media_type='application/x-ndjson',filename='aira-babysit-seed.jsonl')
