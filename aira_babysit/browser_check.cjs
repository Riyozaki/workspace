// Actual dashboard + actual student API worker. No GPU/SFT result is simulated.
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const pp=require('../artifacts/aira_browser/node_modules/puppeteer-core');const chrome=require('../artifacts/aira_browser/node_modules/@sparticuz/chromium');const lambdaFS=require('../artifacts/aira_browser/node_modules/@sparticuz/chromium/build/lambdafs').default;
(async()=>{
 const root=path.resolve(__dirname,'..');const libs=await lambdaFS.inflate(path.join(root,'artifacts/aira_browser/node_modules/@sparticuz/chromium/bin/al2023.tar.br'));
 const browser=await pp.launch({args:chrome.args,executablePath:await chrome.executablePath(),headless:true,env:{...process.env,LD_LIBRARY_PATH:libs+'/lib:'+(process.env.LD_LIBRARY_PATH||''),FONTCONFIG_PATH:'/tmp/fonts'}});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const output=process.argv.includes('--record')?path.join(__dirname,'results/browser_checks.json'):path.join(root,'artifacts/aira_browser/autopilot-replay-'+Date.now()+'.json');
 const result={observed_utc:new Date().toISOString(),scope:'Real dashboard and real SmolLM student data collection; no training/model-quality claim',checks:{}};
 try{
  await page.setViewport({width:1280,height:900});await page.setContent('<body style="margin:0"><iframe sandbox="allow-scripts allow-same-origin" src="http://127.0.0.1:8001" style="border:0;width:100vw;height:100vh"></iframe>');
  const f=await(await page.waitForSelector('iframe')).contentFrame();await f.waitForSelector('#start');await f.waitForFunction(()=>!polling);const prior=await f.evaluate(()=>selected);
  await f.select('#count','12');await f.select('#budget','3600');await f.click('#start');await f.waitForFunction(p=>selected&&selected!==p,{timeout:10000},prior);const id=await f.evaluate(()=>selected);result.run_id=id;
  await f.waitForFunction(async id=>{const r=(await(await fetch('/api/runs/'+id)).json()).run;return r.completed_examples>=1&&r.status==='COLLECTING';},{timeout:30000,polling:200},id);
  await f.evaluate(()=>refresh());await f.waitForFunction(()=>!document.querySelector('#pause').disabled,{timeout:5000});await f.click('#pause');await f.waitForFunction(async id=>{const r=(await(await fetch('/api/runs/'+id)).json()).run;return r.status==='PAUSED'&&!r.worker_running;},{timeout:15000,polling:200},id);
  const paused=await f.evaluate(async id=>(await(await fetch('/api/runs/'+id)).json()).run,id);assert.ok(paused.completed_examples>=1&&paused.completed_examples<12);result.checks.real_pause_mid_collection=true;result.committed_at_pause=paused.completed_examples;
  await f.evaluate(()=>refresh());await f.waitForFunction(()=>!document.querySelector('#resume').disabled,{timeout:5000});await f.click('#resume');
  await f.waitForFunction(async id=>{const r=(await(await fetch('/api/runs/'+id)).json()).run;return r.status==='WAITING_TRAINING'&&!r.worker_running;},{timeout:60000,polling:200},id);
  await f.evaluate(()=>refresh());const final=await f.evaluate(async id=>(await(await fetch('/api/runs/'+id)).json()).run,id);assert.equal(final.completed_examples,12);assert.equal(final.training_executed,false);assert.equal(final.learning_cycle_complete,false);
  result.checks.resume_finishes_data_phase=true;result.checks.not_faking_training=true;result.final_status=final.status;result.active_seconds=final.active_seconds;
  const zipped=await fetch('http://127.0.0.1:8001/api/runs/'+id+'/bundle/download');assert.equal(zipped.status,200);const bytes=Buffer.from(await zipped.arrayBuffer());result.bundle_sha256=crypto.createHash('sha256').update(bytes).digest('hex');result.bundle_bytes=bytes.length;
  const notebook=await fetch('http://127.0.0.1:8001/api/runs/'+id+'/notebook/download');assert.equal(notebook.status,200);const nb=await notebook.json();assert.equal(nb.metadata.aira.bundle_sha256,result.bundle_sha256);assert.equal(nb.metadata.aira.training_executed_in_sandbox,false);result.checks.bundle_and_exact_hash_notebook_ready=true;
  const own=path.join(root,'artifacts/aira_babysit',id);const m=JSON.parse(await fs.readFile(path.join(own,'bundle/manifest.json'),'utf8'));assert.equal(m.holdout_included,false);result.checks.holdout_not_exported=true;
  await page.screenshot({path:path.join(root,'artifacts/aira_browser/autopilot.png'),fullPage:true});await page.setViewport({width:390,height:844});result.checks.mobile_no_horizontal_overflow=await f.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1);assert.ok(result.checks.mobile_no_horizontal_overflow);assert.equal(errors.length,0);result.browser_errors=errors;result.all_required_checks_pass=true;
 }catch(e){result.all_required_checks_pass=false;result.failure=String(e);throw e;}
 finally{await fs.writeFile(output,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
