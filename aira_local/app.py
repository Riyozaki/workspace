"""AIra Local Lab. A real local LM + explicitly separated tool/router pilot."""
from __future__ import annotations
import asyncio,json,os,threading,time,uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import psutil
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .engine import LocalLanguageModel
from .router import BudgetRouter,ROOT,metrics,calibrate
from .train_router import load_data
from .tools import calculate,extract_expression,search_notes,CalculatorError
from .guard import non_regression

ART=ROOT.parent/'artifacts/aira_local';ART.mkdir(parents=True,exist_ok=True)
MODEL_MANIFEST=json.loads((ROOT/'model_manifest.json').read_text()) if (ROOT/'model_manifest.json').exists() else {}


class Telemetry:
 def __init__(self):
  self.process=psutil.Process();self.cpus=len(os.sched_getaffinity(0));self.points=deque(maxlen=90);self.peak_rss=0;self.stop=threading.Event();self.thread=None;self.cpu_percent=0.
 def start(self):
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
  self.model=LocalLanguageModel();self.router=BudgetRouter.load(ROOT/'models/budget_router.json');self.telemetry=Telemetry();self.lock=threading.Lock();self.active_id=None;self.cancel=threading.Event();self.last=None;self.feedback=[];self.training={'status':'idle'};self.router_is_published=True;self.training_attempts=0
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
 state.cancel.set();state.telemetry.stop.set()
 if not task.done():task.cancel()

app=FastAPI(title='AIra Local Lab',lifespan=lifespan)
from .middleware import BodyLimitMiddleware
app.add_middleware(BodyLimitMiddleware,max_bytes=131072)
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
def index():return FileResponse(ROOT/'static/index.html')


@app.get('/api/status')
def status():
 pilot=json.loads((ROOT/'results/router_ablation.json').read_text())
 return {'app':'AIra Local Lab','prototype':True,'model':{'status':state.model.status,'error':state.model.error,'id':'SmolLM2-135M-Instruct','nominal_parameters':135000000,'quantization':'Q4_1','file_bytes':MODEL_MANIFEST.get('gguf_bytes'),'sha256':MODEL_MANIFEST.get('gguf_sha256'),'context':1024,'threads':1,'gpu_layers':0,'load_seconds':state.model.load_seconds,'runtime_system_info':state.model.system_info,'trained_here':False,'russian_validated':False},'router':{'kind':state.router.kind,'parameters':state.router.parameters,'threshold':state.router.threshold,'published_version':state.router_is_published,'scope':'intent classifier, NOT a language model','pilot_holdout':pilot['deployed_holdout'],'pilot_status':'failed to generalize; automatic routing is experimental, not default'},'telemetry':state.telemetry.snapshot(),'busy':state.busy(),'active_id':state.active_id,'last_request':state.last,'training':state.training,'privacy':'No third-party model API. Inference runs in the Arena backend, not in your browser. No chat-content logging or automatic training on conversations.'}


@app.post('/api/chat')
def chat(req:ChatRequest):
 if req.messages[-1].role!='user':raise HTTPException(422,'Last message must be from user')
 if req.mode=='model' and state.model.status!='ready':raise HTTPException(503,'Модель загружается или недоступна. Инструменты можно использовать отдельно.')
 if not state.lock.acquire(blocking=False):raise HTTPException(429,'Уже выполняется одна операция. Дождитесь или остановите её.')
 rid=uuid.uuid4().hex;state.active_id=rid;state.cancel.clear();t0=time.perf_counter();c0=state.telemetry.process.cpu_times();text=req.messages[-1].content
 def stream():
  generated=0;ttfc=None;route=None;used=req.mode;model_metrics={};answer='';error=None
  try:
   route=state.router.route(text)
   if req.mode=='auto':used=route['selected'] if route['accepted_fast_path'] else 'model'
   yield event({'type':'start','id':rid,'used':used,'route':route,'automatic_routing_experimental':req.mode=='auto'})
   if used=='calculator':
    try:
     expression=extract_expression(text);value=calculate(expression);answer=f"{value['expression']} = {value['text']}"
     yield event({'type':'tool','tool':'calculator','source':value['source'],'expression':expression,'value':value['value']})
    except CalculatorError as exc:answer='Калькулятор: '+str(exc)
    ttfc=time.perf_counter()-t0;yield event({'type':'token','text':answer})
   elif used=='notes':
    matches=search_notes(text,[n.model_dump() for n in req.notes]);yield event({'type':'tool','tool':'notes','matches':matches,'source':'lexical local retrieval; not a language-model answer'})
    answer='\n\n'.join(f"[{m['title']}]\n{m['text']}" for m in matches) if matches else 'В переданных заметках совпадений не найдено. Я не искал на диске и не использовал интернет.'
    ttfc=time.perf_counter()-t0;yield event({'type':'token','text':answer})
   else:
    if state.model.status!='ready':raise RuntimeError('Языковая модель ещё не готова. Попробуйте через несколько секунд.')
    for e in state.model.generate([m.model_dump() for m in req.messages],req.max_tokens,state.cancel):
     if e['type']=='token':
      if ttfc is None:ttfc=time.perf_counter()-t0
      answer+=e['text'];yield event(e)
     elif e['type']=='model_end':model_metrics={k:v for k,v in e.items() if k not in ('text','type')};generated=e['generated_tokens']
     else:yield event(e)
  except Exception as exc:
   error=str(exc);yield event({'type':'error','message':error})
  finally:
   if used=='model':
    try:state.model.clear_context()
    except Exception as exc:error='Context cleanup failed: '+str(exc)
   elapsed=time.perf_counter()-t0;c1=state.telemetry.process.cpu_times();cpu=(c1.user+c1.system)-(c0.user+c0.system)
   state.last={'id':rid,'mode':req.mode,'used':used,'request_seconds':elapsed,'server_first_content_seconds':ttfc,'generated_tokens':generated,'cpu_seconds_process':cpu,'cpu_percent_total_capacity_average':100*cpu/max(elapsed,1e-6)/state.telemetry.cpus if elapsed>=.1 else None,'rss_bytes_at_end':state.telemetry.process.memory_info().rss,'energy_joules':None,'model_metrics':model_metrics,'cancelled':state.cancel.is_set(),'error':error,'answer_content_stored':False}
   finished_metrics=state.last
   state.active_id=None;state.lock.release()
  yield event({'type':'done','metrics':finished_metrics})
 return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


@app.post('/api/cancel/{rid}')
def cancel(rid:str):
 if state.active_id!=rid:raise HTTPException(404,'Операция уже завершена')
 state.cancel.set();return {'cancel_requested':True}


@app.get('/api/lab')
def lab():
 report=json.loads((ROOT/'results/router_ablation.json').read_text());rows=load_data()
 return {'report':report,'train_examples':[r for r in rows if r['split']=='train'][:8],'feedback':state.feedback,'training':state.training,'live_router_published':state.router_is_published,'limits':['This pilot trains only the intent router, not SmolLM2.','Pilot holdout generalization failed; no new-architecture or frontier-quality claim.','Feedback examples are training data; live retraining reports development only.']}


@app.post('/api/lab/predict')
def lab_predict(req:PredictionRequest):return state.router.route(req.text)


@app.post('/api/lab/feedback')
def feedback(req:Correction):
 if len(state.feedback)>=30:raise HTTPException(400,'Достигнут лимит 30 исправлений за сессию')
 record=req.model_dump();record['student_before']=state.router.route(req.prompt);record['source']='explicit user teacher correction';state.feedback.append(record)
 return {'added':True,'count':len(state.feedback),'record':record,'language_model_weights_changed':False}


@app.post('/api/lab/train')
def train():
 if not state.feedback:raise HTTPException(400,'Сначала добавьте хотя бы одно исправление учителя')
 if state.training_attempts>=10:raise HTTPException(429,'Лимит 10 учебных запусков в этой демонстрационной сессии')
 if not state.lock.acquire(blocking=False):raise HTTPException(429,'Сначала завершите текущую операцию')
 state.training_attempts+=1
 job_id=uuid.uuid4().hex;started=time.time()
 state.training={'status':'running','started_unix':started,'job_id':job_id};records=[dict(r) for r in state.feedback]
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
    state.router=student;state.router_is_published=False
    student.save(ART/'live_router.json',{'scope':'development-gated live router, NOT independently tested','feedback_n':len(records)})
   state.training={'status':'done','job_id':job_id,'started_unix':started,'fit':result,'before_development':before_development,'development':development,'promoted':promoted,'promotion_reason':'development non-regression gate passed' if promoted else 'development regression: previous router retained','feedback_results':after,'language_model_weights_changed':False,'independent_holdout_evaluated':False}
  except Exception as exc:state.training={'status':'error','job_id':job_id,'error':str(exc)}
  finally:state.lock.release()
 threading.Thread(target=work,daemon=True).start();return {'started':True,'job_id':job_id,'scope':'router only; development metrics only; previous published holdout is NOT a score for the new weights'}


@app.get('/api/lab/export')
def export():
 source=ROOT/'data/babysit_seed.jsonl'
 if not source.exists():raise HTTPException(404,'Seed dataset unavailable')
 return FileResponse(source,media_type='application/x-ndjson',filename='aira-babysit-seed.jsonl')
