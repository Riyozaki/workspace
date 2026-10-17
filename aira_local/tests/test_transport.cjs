const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
const {SSEParser,jsonFetch}=require('../static/transport.js');

test('LF stream survives arbitrary byte-decoded text chunk boundaries',()=>{
 const expected=[{type:'start',id:'a'},{type:'token',text:'Привет 🌿'},{type:'done',metrics:{}}];const got=[];const p=new SSEParser(e=>got.push(e));
 for(const ch of expected.map(e=>'data: '+JSON.stringify(e)+'\n\n').join(''))p.feed(ch);
 p.finish();assert.deepEqual(got,expected);
});
test('CRLF separators split across chunks and final frame without delimiter',()=>{
 const out=[];const p=new SSEParser(e=>out.push(e));for(const s of ['data: {"type":"token","text":"a"}\r','\n\r','\ndata: {"type":"done"}'])p.feed(s);p.finish();assert.deepEqual(out,[{type:'token',text:'a'},{type:'done'}]);
});
test('SSE heartbeats and multi-line JSON data',()=>{
 const out=[];const p=new SSEParser(e=>out.push(e));p.feed(': heartbeat\n\ndata: {\ndata: "type":"token",\ndata: "text":"x"\ndata: }\n\n');p.finish();assert.equal(out.length,1);assert.equal(out[0].text,'x');
});
test('Malformed/truncated JSON produces a visible protocol error',()=>{
 const p=new SSEParser(()=>{});assert.throws(()=>p.feed('data: {oops}\n\n'),/повреждённый/);
 const q=new SSEParser(()=>{});q.feed('data: {"type":');assert.throws(()=>q.finish(),/повреждённый/);
});
test('One event cannot grow without a bound',()=>{
 const p=new SSEParser(()=>{});assert.throws(()=>p.feed('x'.repeat(262145)),/большой/);
 const q=new SSEParser(()=>{});assert.throws(()=>{for(let i=0;i<300;i++)q.feed('data: '+ 'x'.repeat(1000)+'\n');},/большое/);
});
test('Malformed event shape is rejected',()=>{const p=new SSEParser(()=>{});assert.throws(()=>p.feed('data: {"type":4}\n\n'),/Некорректное/);});
test('HTML returned instead of JSON is not swallowed',async()=>{
 const old=global.fetch;global.fetch=async()=>new Response('<html>wrong origin</html>',{headers:{'content-type':'text/html'}});
 try{await assert.rejects(jsonFetch('/api/status'),/HTML вместо JSON/);}finally{global.fetch=old;}
});
test('JSON HTTP errors retain the useful explanation',async()=>{
 const old=global.fetch;global.fetch=async()=>new Response('{"detail":"model unavailable"}',{status:503,headers:{'content-type':'application/json'}});
 try{await assert.rejects(jsonFetch('/api/status'),/model unavailable/);}finally{global.fetch=old;}
});
test('JSON fetch has a real abort timeout',async()=>{
 const old=global.fetch;global.fetch=(_url,opt)=>new Promise((_resolve,reject)=>opt.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError'))));
 try{await assert.rejects(jsonFetch('/api/status',{},20),/вовремя/);}finally{global.fetch=old;}
});
test('Sending is not dependent on iframe allow-forms',()=>{
 const html=fs.readFileSync(require('node:path').join(__dirname,'../static/index.html'),'utf8');const js=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
 assert.match(html,/<button type="button" id="send"/);assert.ok(!js.includes('requestSubmit('));assert.ok(js.includes("$('send').addEventListener('click',requestSend)"));assert.ok(js.includes('e.isComposing'));
});
