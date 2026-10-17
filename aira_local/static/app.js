'use strict';
const $ = id => document.getElementById(id);
const transport = globalThis.AiraTransport;
const state = {mode:'model',history:[],busy:false,requestId:null,status:null,lab:null,connection:'checking',polling:false,currentRequest:null,trainingPending:false,trainingJobId:null};
let toastTimer;
function toast(text,error=false){const el=$('toast');el.textContent=text;el.classList.remove('hidden');el.classList.toggle('error',error);clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.add('hidden'),5500);}
function tab(name){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id==='view-'+name));document.querySelectorAll('.nav').forEach(v=>v.classList.toggle('active',v.dataset.tab===name));$('breadcrumb').textContent={chat:'Диалог',lab:'AI Babysit',about:'Границы прототипа'}[name];if(name==='lab')loadLab();}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
function mode(name){if(state.busy)return;state.mode=name;document.querySelectorAll('#modes button').forEach(b=>b.classList.toggle('selected',b.dataset.mode===name));$('auto-warning').classList.toggle('hidden',name!=='auto');updateSend();}
document.querySelectorAll('#modes button').forEach(b=>b.addEventListener('click',()=>mode(b.dataset.mode)));
document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>{if(state.busy){toast('Сначала завершите текущий запрос.');return;}mode(b.dataset.mode);$('prompt').value=b.dataset.prompt;$('prompt').focus();}));
function unavailableReason(){
 if(state.connection!=='online')return state.connection==='checking'?'Подключаемся к серверу…':'Нет связи с API. Нажмите «Повторить связь». Черновик сохранён.';
 if(state.mode==='model'&&state.status?.model?.status!=='ready')return state.status?.model?.status==='error'?'Модель не загружена. Повторите загрузку или выберите инструмент.':'Модель загружается. Пока доступны калькулятор и заметки.';
 return '';
}
function updateSend(){const reason=unavailableReason();$('send').disabled=state.busy||Boolean(reason);$('send').title=reason||'Отправить';$('prompt').disabled=state.busy;$('stop').classList.toggle('hidden',!state.busy);$('send').classList.toggle('hidden',state.busy);document.querySelectorAll('#modes button,.suggestions button').forEach(b=>b.disabled=state.busy);$('clear').disabled=state.busy;}
function connectionNotice(text,error=false){$('connection-text').textContent=text;$('connection-banner').classList.remove('hidden');$('connection-banner').classList.toggle('connection-error',error);$('retry-model').classList.toggle('hidden',!(state.connection==='online'&&state.status?.model?.status==='error'));}
function bubble(role,text){$('welcome').classList.add('hidden');const box=document.createElement('article');box.className='message '+role;const label=document.createElement('div');label.className='message-label';label.textContent=role==='user'?'ВЫ / ЗАПРОС':'ПОДКЛЮЧЕНИЕ К СЕРВЕРУ';const content=document.createElement('div');content.className='bubble';content.textContent=text;const stats=document.createElement('div');stats.className='message-stats';box.append(label,content,stats);$('messages').append(box);scrollChat();return {box,label,content,stats};}
function scrollChat(){const el=$('chat-scroll');el.scrollTop=el.scrollHeight;}
function seconds(x){return x==null?'—':x<1?`${Math.round(x*1000)} мс`:`${x.toFixed(2)} с`;}
async function api(path,body){return transport.jsonFetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)},8000);}
const defaultNotes=[{id:'training',title:'План обучения',text:'Большое обучение будет перенесено на Kaggle после подготовки данных, контроля качества и расчёта ресурсов. Здесь пока работает неизменённая предобученная SmolLM2 и отдельный маленький роутер.'},{id:'budget',title:'Лимит памяти и железо',text:'Этот стенд: около 4 ГБ системной RAM, два логических CPU. Инференс ограничен одним потоком, контекстом 1024 и максимумом 160 новых токенов. Энергия в джоулях не измеряется.'},{id:'goal',title:'Цель проекта AIra',text:'Полезный локальный агент с малыми затратами. Достигнутый результат нужно подтверждать реальными задачами, а не только прокси-метриками. AI Babysit означает проверяемое обучение на исправлениях учителя.'}];
let notes=defaultNotes.map(n=>({...n}));
$('notes-text').value=notes.map(n=>n.title+'\n'+n.text).join('\n\n');
$('save-notes').addEventListener('click',()=>{notes=$('notes-text').value.split(/\n\s*\n/).map((b,i)=>{const lines=b.trim().split('\n');return {id:'custom-'+i,title:lines.shift().slice(0,120),text:lines.join('\n').slice(0,6000)};}).filter(n=>n.title).slice(0,8);$('notes-saved').textContent=' Применено только в этой вкладке';toast('Заметки обновлены. На диске и в обучающих данных они не сохраняются.');});
$('clear').addEventListener('click',()=>{if(state.busy)return;state.history=[];$('messages').replaceChildren();$('welcome').classList.remove('hidden');});
function requestSend(){if(state.busy)return;const reason=unavailableReason();if(reason){toast(reason,true);return;}sendMessage();}
$('send').addEventListener('click',requestSend);
$('chat-form').addEventListener('submit',e=>{e.preventDefault();requestSend();});
$('prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){e.preventDefault();requestSend();}});
$('stop').addEventListener('click',async()=>{
 const job=state.currentRequest;if(!job)return;job.userCancelled=true;$('stop').disabled=true;
 if(!job.id){job.controller.abort();return;}
 job.cancelFallback=setTimeout(()=>job.controller.abort(),2200);
 try{await api('/api/cancel/'+job.id,{});}catch{job.controller.abort();}
});
function addRetry(message,text,requestMode){const b=document.createElement('button');b.type='button';b.className='retry-message';b.textContent='Повторить';b.addEventListener('click',async()=>{if(state.busy)return;mode(requestMode);$('prompt').value=text;await poll();requestSend();});message.stats.append(' ',b);}
async function sendMessage(){
 const text=$('prompt').value.trim();if(!text||state.busy)return;
 const requestMode=state.mode;const inputMessages=[...state.history.slice(-6),{role:'user',content:text}];
 const job={controller:new AbortController(),id:null,userCancelled:false,timedOut:false,done:false,answer:'',error:null,serverMetrics:null,cancelFallback:null,idleTimer:null,contextDropped:0};
 state.currentRequest=job;state.busy=true;state.requestId=null;updateSend();$('stop').disabled=false;
 const user=bubble('user',text);const msg=bubble('assistant','');msg.box.classList.add('typing');const browserStart=performance.now();
 const totalTimer=setTimeout(()=>{job.timedOut=true;job.controller.abort();},65000);
 function armIdle(){clearTimeout(job.idleTimer);job.idleTimer=setTimeout(()=>{job.timedOut=true;job.controller.abort();},25000);}
 function receive(ev){
  if(ev.type==='start'){
   job.id=ev.id;state.requestId=ev.id;$('prompt').value='';
   const names={model:'SMOLLM2 135M / МОДЕЛЬ',calculator:'КАЛЬКУЛЯТОР / ДЕТЕРМИНИРОВАННЫЙ ИНСТРУМЕНТ',notes:'ЗАМЕТКИ / ЛОКАЛЬНЫЙ ПОИСК'};
   msg.label.textContent=names[ev.used]||ev.used;if(requestMode==='auto')msg.label.textContent+=' · ЭКСПЕРИМЕНТАЛЬНЫЙ ВЫБОР';
  }else if(ev.type==='model_start'){job.contextDropped=ev.dropped_history_messages||0;}else if(ev.type==='token'){if(typeof ev.text!=='string')throw new Error('Некорректный фрагмент текста в потоке.');job.answer+=ev.text;msg.content.textContent=job.answer;scrollChat();}
  else if(ev.type==='error'){job.error=ev.message||'Ошибка сервера';}
  else if(ev.type==='done'){
   if(!ev.metrics||typeof ev.metrics.request_seconds!=='number')throw new Error('Повреждены завершающие метрики ответа.');
   job.done=true;job.serverMetrics=ev.metrics;job.error=job.error||ev.metrics.error;renderLast(ev.metrics);
  }
 }
 try{
  armIdle();
  const body=JSON.stringify({messages:inputMessages,mode:requestMode,max_tokens:Number($('max-tokens').value),notes:(requestMode==='notes'||requestMode==='auto')?notes:[]});
  if(new TextEncoder().encode(body).length>131072)throw new Error('Сообщения и заметки вместе превышают бюджет 128 KiB. Сократите текст или начните новый диалог.');
  const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body,signal:job.controller.signal,cache:'no-store'});
  if(!response.ok)throw new Error(await transport.responseError(response));
  if(!(response.headers.get('content-type')||'').includes('text/event-stream'))throw new Error('Вместо ответа API получена HTML-страница. Откройте Live Preview приложения и проверьте связь.');
  const reader=response.body.getReader(),decoder=new TextDecoder(),parser=new transport.SSEParser(receive);
  while(true){const {done,value}=await reader.read();if(done)break;armIdle();parser.feed(decoder.decode(value,{stream:true}));}
  parser.feed(decoder.decode());parser.finish();
  if(!job.done)throw new Error(job.error||'Соединение оборвалось до завершения ответа. Запрос можно повторить.');
  if(job.error)throw new Error(job.error);
  const m=job.serverMetrics;msg.stats.textContent=`Сервер ${seconds(m.request_seconds)} · браузер ${((performance.now()-browserStart)/1000).toFixed(2)} с${m.generated_tokens?' · '+m.generated_tokens+' ток.':' · без генерации токенов'}${m.cancelled?' · остановлено':''}${job.contextDropped?' · контекст: −'+job.contextDropped+' сообщ.':''}`;
  if(!job.answer)msg.content.textContent=m.cancelled?'Генерация остановлена.':'Модель завершила генерацию без текста. Это пустой ответ модели, не потерянное сообщение.';
  if(job.answer)state.history=[...inputMessages,{role:'assistant',content:job.answer}].slice(-16);
 }catch(err){
  job.controller.abort();
  const cancelled=job.userCancelled;
  const message=cancelled?'Остановлено пользователем.':job.timedOut?'Ответ не пришёл вовремя. Черновик сохранён; проверьте связь и повторите.':err.message||'Не удалось отправить сообщение.';
  if(!cancelled){msg.box.classList.add('error');user.label.textContent='ВЫ / ЗАПРОС НЕ ЗАВЕРШЁН';}
  if(!job.answer)msg.content.textContent=message;
  else{const note=document.createElement('div');note.className='stream-error';note.textContent=message;msg.box.append(note);}
  msg.stats.textContent=cancelled?'Остановлено в браузере':'Запрос не добавлен в контекст модели';
  $('prompt').value=text;if(!cancelled){toast(message,true);addRetry(msg,text,requestMode);}
  if(job.id&&!job.done)api('/api/cancel/'+job.id,{}).catch(()=>{});
 }finally{
  clearTimeout(totalTimer);clearTimeout(job.idleTimer);clearTimeout(job.cancelFallback);msg.box.classList.remove('typing');
  if(state.currentRequest===job){state.currentRequest=null;state.busy=false;state.requestId=null;}
  updateSend();$('stop').disabled=false;$('prompt').focus();poll();
 }
}
function renderLast(m){if(!m)return;$('last-time').textContent=seconds(m.request_seconds);$('first-time').textContent=seconds(m.server_first_content_seconds);$('tokens').textContent=m.used==='model'?m.generated_tokens+' ток.':'инструмент';const speed=m.model_metrics?.generation_tokens_per_second;$('speed').textContent=speed?speed.toFixed(1)+' ток/с':'не применимо';}
async function poll(){
 if(state.polling)return;state.polling=true;
 try{
  const s=await transport.jsonFetch('/api/status',{},4500);
  if(!s.model||typeof s.model.status!=='string'||!s.telemetry)throw new Error('Некорректный ответ status API. Возможно, открыт не сервер приложения.');
  state.status=s;state.connection='online';const badge=$('model-status');const ms=s.model.status;
  badge.className='status-chip '+(ms==='ready'?'':ms==='error'?'error':'loading');badge.replaceChildren();const dot=document.createElement('i');badge.append(dot,document.createTextNode(ms==='ready'?'Готова':ms==='error'?'Ошибка модели':'Загружается'));
  if(ms==='error')connectionNotice('Модель не загрузилась: '+(s.model.error||'причина не указана')+'. Инструменты доступны отдельно.',true);
  else if(ms!=='ready')connectionNotice('Модель загружается. Пока можно выбрать калькулятор или заметки.');
  else{$('connection-banner').classList.add('hidden');$('retry-model').classList.add('hidden');}
  const t=s.telemetry;$('rss').textContent=(t.rss_bytes/1048576).toFixed(1);$('cpu').textContent=t.cpu_percent_total_capacity.toFixed(1);$('ram-bar').style.width=Math.min(100,100*t.rss_bytes/t.system_memory_bytes)+'%';$('ram-caption').textContent='из '+(t.system_memory_bytes/1073741824).toFixed(2)+' GiB';$('peak').textContent='peak '+(t.peak_sampled_rss_bytes/1048576).toFixed(0)+' MiB';$('cpu-limit').textContent=t.logical_cpu_limit+' лог. CPU';
  const pts=(t.history||[]).slice(-50);if(pts.length>1)$('cpu-path').setAttribute('d',pts.map((p,i)=>(i?'L':'M')+(i/(pts.length-1)*240).toFixed(1)+' '+(49-Math.min(100,p.cpu_percent_total_capacity)/100*46).toFixed(1)).join(' '));
  if(!state.busy)renderLast(s.last_request);if(s.training&&(s.training.status==='done'||s.training.status==='error'))renderTraining(s.training);
 }catch(e){state.connection='offline';$('model-status').className='status-chip error';$('model-status').textContent='Нет связи';connectionNotice('Не удалось связаться с API: '+(e.message||'ошибка сети')+' Черновик не потерян.',true);}
 finally{state.polling=false;updateSend();}
}
$('reconnect').addEventListener('click',()=>{poll();});
$('retry-model').addEventListener('click',async()=>{try{await api('/api/model/retry',{});poll();}catch(e){toast(e.message,true);}});
window.addEventListener('online',()=>poll());document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
window.addEventListener('pagehide',()=>{const job=state.currentRequest;if(job){job.userCancelled=true;job.controller.abort();if(job.id)fetch('/api/cancel/'+job.id,{method:'POST',keepalive:true}).catch(()=>{});}});
setInterval(()=>{if(!document.hidden||state.busy)poll();},2000);poll();
function pct(n){return (100*n).toFixed(1)+'%';}
async function loadLab(){try{const d=await api('/api/lab');state.lab=d;const r=d.report;const values=[['ПАРАМЕТРЫ УЧЕНИКА',r.deployed_holdout.parameters.toLocaleString('ru'),'классификатор, не языковая модель'],['ПЕРВИЧНЫЙ TEST',pct(r.deployed_holdout.accuracy),'36 новых формулировок · слабое качество'],['УЧЕБНЫЕ ПРИМЕРЫ','144','36 development / 36 test отдельно']];$('lab-summary').replaceChildren();for(const [title,value,caption]of values){const box=document.createElement('div');box.className='summary-box';const l=document.createElement('label');l.textContent=title;const v=document.createElement('strong');v.textContent=value;const small=document.createElement('small');small.textContent=caption;box.append(l,v,small);$('lab-summary').append(box);}$('ablation-rows').replaceChildren();for(const row of r.all_runs){const tr=document.createElement('tr');[row.kind==='linear'?'Линейный контроль':'Общие веса · 2 шага',row.seed,row.fit.parameters,pct(row.development.accuracy),pct(row.holdout.accuracy),row.holdout.wrong_fast_paths].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td);});$('ablation-rows').append(tr);}$('feedback-count').textContent=d.feedback.length;if(!d.live_router_published)$('prediction').textContent='Live-ученик обновлён. Таблица ниже относится к исходному checkpoint, не к новым весам.';if(d.training.status!=='idle')renderTraining(d.training);}catch(e){toast(e.message,true);}}
$('inspect').addEventListener('click',async()=>{try{const d=await api('/api/lab/predict',{text:$('lab-prompt').value});$('prediction').textContent=`Прогноз: ${d.predicted}\nScore: ${d.score.toFixed(3)} (не калиброванная вероятность)\nПорог: ${d.threshold.toFixed(2)}\nБыстрый путь: ${d.accepted_fast_path?'да':'нет, переход к LM'}\nВремя: ${d.elapsed_ms.toFixed(2)} мс`; }catch(e){toast(e.message,true);}});
$('add-correction').addEventListener('click',async()=>{try{const d=await api('/api/lab/feedback',{prompt:$('lab-prompt').value,target:$('teacher-target').value,why:$('teacher-why').value});$('feedback-count').textContent=d.count;toast('Исправление добавлено явно. Веса языковой модели не меняются.');}catch(e){toast(e.message,true);}});
$('train-router').addEventListener('click',async()=>{
 const el=$('training-result');el.classList.remove('hidden');el.dataset.jobId='';el.dataset.status='running';el.textContent='Запускаем настоящий NumPy backward…';$('train-router').disabled=true;state.trainingPending=true;
 try{const d=await api('/api/lab/train',{});state.trainingJobId=d.job_id;state.trainingPending=false;lastTraining='';poll();}
 catch(e){state.trainingPending=false;$('train-router').disabled=false;el.textContent=e.message;el.dataset.status='error';toast(e.message,true);}
});
let lastTraining='';function renderTraining(t){
 if(state.trainingPending)return;if(state.trainingJobId&&t.job_id!==state.trainingJobId)return;
 const key=JSON.stringify(t);if(key===lastTraining)return;lastTraining=key;const el=$('training-result');el.classList.remove('hidden');
 if(t.status==='error'){el.textContent=t.error;el.dataset.status='error';el.dataset.jobId=t.job_id||'';$('train-router').disabled=false;return;}
 if(t.status!=='done')return;$('train-router').disabled=false;el.dataset.jobId=t.job_id||'';el.dataset.status='done';
 const lines=[`Обучено: ${t.fit.steps} шагов за ${t.fit.train_seconds.toFixed(3)} с`,`Development accuracy: ${pct(t.before_development.accuracy)} → ${pct(t.development.accuracy)}`,t.promoted?'Кандидат принят по development. Независимого подтверждения улучшения нет.':'Кандидат ОТКЛОНЁН: регрессия на development. Предыдущие веса сохранены.','Веса SmolLM2 НЕ изменены. Независимый test новых весов НЕ выполнен.','Результат кандидата на исправленных УЧЕБНЫХ примерах:'];
 for(const x of t.feedback_results)lines.push(`• ${x.before.predicted} → ${x.after.predicted} (эталон: ${x.expected})`);el.textContent=lines.join('\n');
}
// Inline SVG, not font-dependent Unicode symbols. No user content enters HTML.
const iconPaths={chat:'<path d="M20 11a8 8 0 0 1-8 8H5l-3 3V11a9 9 0 0 1 18 0Z"/><path d="M7 10h8M7 14h5"/>',lab:'<path d="M9 3h6M10 3v6l-6 10a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2L14 9V3M7 16h10"/>',about:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',arrow:'<path d="M6 18 18 6M6 6h12v12"/>',send:'<path d="m6 11 6-6 6 6M12 5v15"/>',calculator:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h1M15 12h1M8 16h1M15 16h1"/>',notes:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',reset:'<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>'};
function icon(name){const el=document.createElementNS('http://www.w3.org/2000/svg','svg');el.setAttribute('viewBox','0 0 24 24');el.setAttribute('fill','none');el.setAttribute('stroke','currentColor');el.setAttribute('stroke-width','1.5');el.setAttribute('stroke-linecap','round');el.setAttribute('stroke-linejoin','round');el.setAttribute('aria-hidden','true');el.innerHTML=iconPaths[name]||iconPaths.chat;return el;}
document.querySelectorAll('.nav').forEach(b=>{b.setAttribute('aria-label',{chat:'Диалог',lab:'AI Babysit',about:'Границы прототипа'}[b.dataset.tab]);b.querySelector('.nav-icon').replaceChildren(icon(b.dataset.tab));});
$('send').replaceChildren(icon('send'));document.querySelector('.welcome-icon').replaceChildren(icon('arrow'));document.querySelector('.shield').replaceChildren(icon('about'));
document.querySelectorAll('.suggestions button').forEach(b=>{b.querySelector('span').replaceChildren(icon(b.dataset.mode==='model'?'chat':b.dataset.mode));b.querySelector('b').replaceChildren(icon('arrow'));});
const modeLabels={model:'Модель',calculator:'Калькулятор',notes:'Заметки',auto:'Авто · опыт'};
document.querySelectorAll('#modes button').forEach(b=>b.replaceChildren(icon(b.dataset.mode==='model'?'chat':b.dataset.mode==='auto'?'lab':b.dataset.mode),document.createTextNode(modeLabels[b.dataset.mode])));
