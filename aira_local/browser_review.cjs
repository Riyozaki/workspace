// Review regression suite: REAL backend in a sandboxed iframe; injected faults
// are explicitly transport tests, never evidence of model quality/performance.
const fs=require('node:fs/promises');const path=require('node:path');const assert=require('node:assert/strict');
const puppeteer=require('../artifacts/aira_browser/node_modules/puppeteer-core');
const chromium=require('../artifacts/aira_browser/node_modules/@sparticuz/chromium');
const lambdaFS=require('../artifacts/aira_browser/node_modules/@sparticuz/chromium/build/lambdafs').default;
(async()=>{
 const root=path.resolve(__dirname,'..'),out=process.argv.includes('--record')?path.join(__dirname,'results/review_001'):path.join(root,'artifacts/aira_browser/review_runs',new Date().toISOString().replace(/[:.]/g,'-'));await fs.mkdir(out,{recursive:true});const shots=path.join(root,'artifacts/aira_browser/review_001');await fs.mkdir(shots,{recursive:true});
 const libs=await lambdaFS.inflate(path.join(root,'artifacts/aira_browser/node_modules/@sparticuz/chromium/bin/al2023.tar.br'));
 const browser=await puppeteer.launch({args:chromium.args,executablePath:await chromium.executablePath(),headless:true,env:{...process.env,LD_LIBRARY_PATH:libs+'/lib:'+(process.env.LD_LIBRARY_PATH||''),FONTCONFIG_PATH:'/tmp/fonts'}});
 const page=await browser.newPage();const errors=[],consoleErrors=[],posts=[],held=[];let fault=null;
 page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text());});
 await page.setRequestInterception(true);
 page.on('request',r=>{
  if(r.url().endsWith('/api/chat')&&r.method()==='POST'){try{const d=JSON.parse(r.postData());posts.push({mode:d.mode,notes_count:d.notes?.length||0});}catch{}}
  if(r.url().endsWith('/api/status')&&fault==='status-offline')return r.abort('internetdisconnected');
  if(r.url().endsWith('/api/status')&&fault==='status-html')return r.respond({status:200,contentType:'text/html',body:'<h1>Not the API origin</h1>'});
  if(r.url().endsWith('/api/chat')&&r.method()==='POST'&&fault==='stall-post'){held.push(r);return;}
  if(r.url().endsWith('/api/chat')&&r.method()==='POST'&&fault==='post-html')return r.respond({status:502,contentType:'text/html',body:'<h1>Proxy failure</h1>'});
  if(r.url().endsWith('/api/chat')&&r.method()==='POST'&&fault==='truncated-sse')return r.respond({status:200,contentType:'text/event-stream',body:'data: {"type":"start","id":"injected-negative-test","used":"calculator"}\n\ndata: {"type":"token","text":"partial transport fixture"}\n\n'});
  return r.continue();
 });
 const result={tested_at_utc:new Date().toISOString(),browser:await browser.version(),scope:'Real local backend embedded with sandbox allow-scripts allow-same-origin; user external proxy flags not directly inspected',iframe_sandbox:'allow-scripts allow-same-origin',checks:{},fault_injection_tests:{}};
 async function input(f,text){await f.$eval('#prompt',(e,t)=>{e.value=t;},text);}
 async function send(f,text,mode='calculator',enter=false){
  await f.click(`#modes button[data-mode="${mode}"]`);await input(f,text);const old=await f.$$eval('#messages .message.assistant',a=>a.length);const count=posts.length;
  if(enter){await f.focus('#prompt');await page.keyboard.press('Enter');}else await f.click('#send');
  await f.waitForFunction(n=>document.querySelectorAll('#messages .message.assistant').length===n+1,{timeout:5000},old);
  await f.waitForFunction(()=>!state.busy,{timeout:20000});
  assert.equal(posts.length,count+1,'one action must issue exactly one POST');
  return f.$eval('#messages .message.assistant:last-child',e=>({text:e.querySelector('.bubble').textContent,label:e.querySelector('.message-label').textContent,stats:e.querySelector('.message-stats').textContent,error:e.classList.contains('error')}));
 }
 try{
  await page.setViewport({width:1380,height:920});
  await page.setContent('<html><body style="margin:0"><iframe sandbox="allow-scripts allow-same-origin" src="http://127.0.0.1:8000/" style="border:0;width:100vw;height:100vh"></iframe></body></html>');
  const handle=await page.waitForSelector('iframe');const f=await handle.contentFrame();await f.waitForFunction(()=>state.connection==='online'&&state.status.model.status==='ready',{timeout:20000});
  result.checks.ready_in_embedded_preview=true;
  let r=await send(f,'Посчитай -3+5');assert.equal(r.text,'-3+5 = 2');assert.ok(r.label.includes('ИНСТРУМЕНТ'));result.checks.click_sends_inside_no_forms_iframe=true;
  r=await send(f,'Посчитай (18+7)*4','calculator',true);assert.equal(r.text,'(18+7)*4 = 100');result.checks.enter_sends_inside_no_forms_iframe=true;
  const beforeIME=posts.length;await input(f,'IME draft');await f.$eval('#prompt',e=>e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true})));await new Promise(r=>setTimeout(r,100));assert.equal(posts.length,beforeIME);result.checks.ime_enter_does_not_accidentally_send=true;
  r=await send(f,'Explain what a CPU does in one sentence.','model');assert.ok(!r.error&&r.text.length>0);assert.ok(r.label.includes('SMOLLM2'));
  const last=await f.evaluate(async()=> (await (await fetch('/api/status')).json()).last_request);assert.ok(last.generated_tokens>0);assert.equal(last.error,null);result.checks.real_model_response_in_embedded_preview={generated_tokens:last.generated_tokens,text:r.text};
  r=await send(f,'Найди в заметках план обучения','notes');assert.ok(r.text.includes('Kaggle'));result.checks.local_notes_work=true;
  result.checks.notes_not_sent_in_model_or_calculator=posts.filter(r=>r.mode==='model'||r.mode==='calculator').every(r=>r.notes_count===0);assert.ok(result.checks.notes_not_sent_in_model_or_calculator);
  // Network failures are synthetic transport negatives, not model tests.
  fault='status-offline';await input(f,'draft kept while API offline');await f.evaluate(()=>poll());await f.waitForFunction(()=>state.connection==='offline');assert.ok(await f.$eval('#connection-banner',e=>!e.classList.contains('hidden')));assert.equal(await f.$eval('#prompt',e=>e.value),'draft kept while API offline');result.fault_injection_tests.status_network_error_visible_and_draft_kept=true;
  fault=null;await f.click('#reconnect');await f.waitForFunction(()=>state.connection==='online');result.checks.reconnect_recovers=true;
  fault='status-html';await f.evaluate(()=>poll());await f.waitForFunction(()=>state.connection==='offline');assert.ok((await f.$eval('#connection-text',e=>e.textContent)).includes('HTML'));result.fault_injection_tests.wrong_origin_html_visible=true;fault=null;await f.click('#reconnect');await f.waitForFunction(()=>state.connection==='online');
  const historyBefore=await f.evaluate(()=>JSON.stringify(state.history));fault='post-html';r=await send(f,'Посчитай 7+8');assert.ok(r.error&&r.text.includes('HTTP 502'));assert.equal(await f.$eval('#prompt',e=>e.value),'Посчитай 7+8');assert.equal(await f.evaluate(()=>JSON.stringify(state.history)),historyBefore);result.fault_injection_tests.post_failure_restores_draft_without_poisoning_history=true;
  fault='truncated-sse';r=await send(f,'Посчитай 9+4');assert.ok(r.error);assert.equal(await f.$eval('#prompt',e=>e.value),'Посчитай 9+4');assert.equal(await f.evaluate(()=>JSON.stringify(state.history)),historyBefore);result.fault_injection_tests.truncated_stream_releases_ui_and_preserves_history=true;
  fault='stall-post';await f.click('#modes button[data-mode="calculator"]');await input(f,'Посчитай 11+12');await f.click('#send');await f.waitForFunction(()=>state.busy&&state.requestId===null);await f.click('#stop');await f.waitForFunction(()=>!state.busy,{timeout:5000});assert.equal(await f.$eval('#prompt',e=>e.value),'Посчитай 11+12');result.fault_injection_tests.stop_before_first_response_restores_draft=true;fault=null;for(const r of held){try{await r.abort();}catch{}}
  r=await send(f,'Посчитай 7+8');assert.equal(r.text,'7+8 = 15');result.checks.send_after_transport_failures=true;
  const contextHistory=await f.evaluate(()=>JSON.stringify(state.history));const longPrompt='жщюя'.repeat(500);r=await send(f,longPrompt,'model');assert.ok(r.error);assert.equal(await f.$eval('#prompt',e=>e.value),longPrompt);assert.equal(await f.evaluate(()=>JSON.stringify(state.history)),contextHistory);result.checks.real_context_overflow_is_visible_and_does_not_poison_history=true;
  r=await send(f,'Посчитай 3*3');assert.equal(r.text,'3*3 = 9');
  // Real early-disconnect regression: abort after the first SSE bytes.
  await f.evaluate(async()=>{const c=new AbortController();try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:'Write a long story about a small robot.'}],mode:'model',max_tokens:160}),signal:c.signal});const reader=r.body.getReader();await reader.read();c.abort();}catch(e){if(e.name!=='AbortError')throw e;}});
  await f.waitForFunction(async()=>!(await(await fetch('/api/status')).json()).busy,{timeout:8000});r=await send(f,'Посчитай 6*7');assert.equal(r.text,'6*7 = 42');result.checks.real_disconnect_releases_model_gate_and_next_send_works=true;
  // Actual cancel button, not a mocked successful model response.
  await f.click('#modes button[data-mode="model"]');await input(f,'Write a long story about a robot learning to garden.');await f.select('#max-tokens','160');await f.click('#send');await f.waitForFunction(()=>state.requestId!==null);await f.click('#stop');await f.waitForFunction(()=>!state.busy,{timeout:8000});await f.waitForFunction(async()=>!(await(await fetch('/api/status')).json()).busy,{timeout:8000});result.checks.cancel_releases_client_and_server=true;
  r=await send(f,'Посчитай 8*8');assert.equal(r.text,'8*8 = 64');result.checks.send_after_cancel_works=true;
  await f.click('.nav[data-tab="lab"]');await f.waitForSelector('#ablation-rows tr');
  result.checks.all_six_historical_control_runs_visible=(await f.$$('#ablation-rows tr')).length===6;assert.ok(result.checks.all_six_historical_control_runs_visible);
  const previousFeedback=await f.$eval('#feedback-count',e=>Number(e.textContent));await f.click('#add-correction');await f.waitForFunction(n=>Number(document.querySelector('#feedback-count').textContent)===n+1,{},previousFeedback);
  const trainingResponse=page.waitForResponse(r=>r.url().endsWith('/api/lab/train')&&r.request().method()==='POST');await f.click('#train-router');const trainingJob=await(await trainingResponse).json();
  await f.waitForFunction(id=>{const e=document.querySelector('#training-result');return e.dataset.jobId===id&&e.dataset.status==='done';},{timeout:15000},trainingJob.job_id);
  const training=await f.evaluate(async()=> (await(await fetch('/api/lab')).json()).training);assert.equal(training.language_model_weights_changed,false);assert.equal(training.independent_holdout_evaluated,false);
  result.checks.actual_teacher_feedback_job_finished={job_id:training.job_id,promoted:training.promoted,language_model_weights_changed:false,independent_holdout_evaluated:false};
  await page.screenshot({path:path.join(shots,'embedded-babysit.png'),fullPage:true});await f.click('.nav[data-tab="chat"]');
  await page.screenshot({path:path.join(shots,'embedded-desktop.png'),fullPage:true});
  await page.setViewport({width:390,height:844});await f.waitForFunction(()=>innerWidth<500);result.checks.mobile_no_horizontal_overflow=await f.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1);assert.ok(result.checks.mobile_no_horizontal_overflow);await page.screenshot({path:path.join(shots,'embedded-mobile.png'),fullPage:true});
  result.browser_errors=errors;result.blocked_form_errors=consoleErrors.filter(e=>e.includes('Blocked form submission'));assert.equal(errors.length,0);assert.equal(result.blocked_form_errors.length,0);
  result.all_required_checks_pass=true;
 }catch(e){result.all_required_checks_pass=false;result.failure=String(e);result.browser_errors=errors;throw e;}
 finally{await fs.writeFile(path.join(out,'browser_checks.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
