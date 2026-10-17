"""Real CPU inference. No remote API, canned model replies or answer cache."""
from __future__ import annotations
import hashlib,itertools,json,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MODEL=ROOT.parent/'artifacts/aira_local/models/SmolLM2-135M-Instruct.Q4_1.gguf'
SYSTEM='You are a small local assistant. Be brief, factual and honest about uncertainty. Never claim to have used a tool or changed files. If you cannot answer, say so.'


class LocalLanguageModel:
 def __init__(self):self.model=None;self.status='not_loaded';self.error=None;self.load_seconds=None;self.system_info=None;self.load_lock=threading.Lock()
 def load(self):
  with self.load_lock:
   if self.model is not None and self.status=='ready':return
   self.status='loading';self.error=None;t=time.perf_counter();candidate=None
   try:
    from llama_cpp import Llama,llama_print_system_info
    if not MODEL.is_file():raise FileNotFoundError('Файл весов отсутствует. Выполните bash aira_local/setup.sh в среде сервера.')
    manifest=json.loads((ROOT/'model_manifest.json').read_text());h=hashlib.sha256()
    with MODEL.open('rb') as stream:
     for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    if h.hexdigest()!=manifest['gguf_sha256']:raise ValueError('SHA-256 весов не совпал с опубликованным manifest. Повторите setup.')
    candidate=Llama(model_path=str(MODEL),n_ctx=1024,n_batch=64,n_threads=1,n_threads_batch=1,n_gpu_layers=0,use_mmap=True,use_mlock=False,verbose=False,seed=42)
    stop_ids={candidate.token_eos()}
    for word in (b'<|im_end|>',b'<|endoftext|>'):
     ids=candidate.tokenize(word,add_bos=False,special=True)
     if len(ids)==1:stop_ids.add(ids[0])
    info=llama_print_system_info();self.system_info=info.decode() if isinstance(info,bytes) else str(info)
    self.model=candidate;self.stop_ids=stop_ids;self.load_seconds=time.perf_counter()-t;self.status='ready'
   except Exception as exc:
    if candidate is not None:
     try:candidate.close()
     except Exception:pass
    self.model=None;self.error=str(exc);self.status='error';raise
 def clear_context(self):
  if self.model is None:return
  self.model.reset()
  # Pinned llama-cpp-python0.3.7 context API; do not reuse another request's KV.
  if hasattr(self.model._ctx,'kv_cache_clear'):self.model._ctx.kv_cache_clear()
  ids=getattr(self.model,'_input_ids',None)
  if ids is not None:ids.fill(0)
 def prompt(self,messages,max_new_tokens):
  history=[{'role':m['role'],'content':m['content']} for m in messages if m['role'] in ('user','assistant')][-8:]
  if not history or history[-1]['role']!='user':raise ValueError('Last message must be a user prompt')
  dropped=0
  while len(history)>1 and history[0]['role']!='user':history.pop(0);dropped+=1
  while True:
   text=f'<|im_start|>system\n{SYSTEM}<|im_end|>\n'
   for m in history:
    safe=m['content'].replace('<|','‹|')
    text+=f'<|im_start|>{m["role"]}\n{safe}<|im_end|>\n'
   text+='<|im_start|>assistant\n';tokens=self.model.tokenize(text.encode(),add_bos=False,special=True)
   if len(tokens)+max_new_tokens+8<=1024:return tokens,dropped
   if len(history)==1:raise ValueError('Сообщение слишком длинное для контекста 1024 токена. Сократите текст или начните новый диалог.')
   history.pop(0);dropped+=1
   while len(history)>1 and history[0]['role']!='user':history.pop(0);dropped+=1
 def generate(self,messages,max_new_tokens=96,cancel=None,deadline=None):
  if self.model is None:raise RuntimeError('Language model is not loaded')
  tokens,dropped=self.prompt(messages,max_new_tokens);t=time.perf_counter();ids=[];previous='';first_token=None;first_content=None
  yield {'type':'model_start','prompt_tokens':len(tokens),'dropped_history_messages':dropped}
  for token in itertools.islice(self.model.generate(tokens,top_k=40,top_p=.9,temp=.4,repeat_penalty=1.1,reset=True),max_new_tokens):
   if deadline is not None and time.perf_counter()>=deadline:
    if cancel is not None:cancel.set()
    break
   if cancel is not None and cancel.is_set():break
   if token in self.stop_ids:break
   ids.append(token)
   if first_token is None:first_token=time.perf_counter()-t
   full=self.model.detokenize(ids).decode('utf-8',errors='ignore');piece=full[len(previous):];previous=full
   if piece:
    if first_content is None:first_content=time.perf_counter()-t
    yield {'type':'token','text':piece,'generated_tokens':len(ids)}
  seconds=time.perf_counter()-t
  yield {'type':'model_end','text':previous,'generated_tokens':len(ids),'generation_seconds':seconds,'generation_tokens_per_second':len(ids)/seconds if seconds else None,'first_native_token_seconds':first_token,'first_content_seconds':first_content,'prompt_tokens':len(tokens),'cancelled':bool(cancel is not None and cancel.is_set()),'dropped_history_messages':dropped}
