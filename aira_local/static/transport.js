/* Pure transport helpers. Native form submission is deliberately not used. */
(function(root){
 'use strict';
 class SSEParser {
  constructor(onEvent){this.onEvent=onEvent;this.buffer='';this.lines=[];this.eventBytes=0;}
  feed(text){
   this.buffer+=text;
   if(this.buffer.length>262144)throw new Error('Слишком большой фрагмент потока ответа.');
   while(true){
    let pos=-1;for(let i=0;i<this.buffer.length;i++){if(this.buffer[i]==='\n'||this.buffer[i]==='\r'){pos=i;break;}}
    if(pos<0)break;
    if(this.buffer[pos]==='\r'&&pos===this.buffer.length-1)break;
    const line=this.buffer.slice(0,pos);const step=this.buffer[pos]==='\r'&&this.buffer[pos+1]==='\n'?2:1;
    this.buffer=this.buffer.slice(pos+step);this.line(line);
   }
  }
  line(line){
   if(line===''){this.dispatch();return;}
   if(line.startsWith(':'))return;
   this.eventBytes+=line.length;if(this.eventBytes>262144)throw new Error('Слишком большое событие потока.');
   if(line==='data')this.lines.push('');
   else if(line.startsWith('data:'))this.lines.push(line.slice(line[5]===' '?6:5));
  }
  dispatch(){
   if(!this.lines.length)return;
   const data=this.lines.join('\n');this.lines=[];this.eventBytes=0;
   let parsed;try{parsed=JSON.parse(data);}catch{throw new Error('Сервер прислал повреждённый поток ответа. Повторите запрос.');}
   if(!parsed||typeof parsed.type!=='string')throw new Error('Некорректное событие в потоке ответа.');
   this.onEvent(parsed);
  }
  finish(){
   if(this.buffer){let last=this.buffer;if(last.endsWith('\r'))last=last.slice(0,-1);this.line(last);this.buffer='';}
   this.dispatch();
  }
 }
 async function responseError(response){
  const text=await response.text();
  try{const d=JSON.parse(text);return typeof d.detail==='string'?d.detail:JSON.stringify(d.detail||d.error||d);}
  catch{return `HTTP ${response.status}: сервер вернул не JSON. Проверьте подключение к Live Preview.`;}
 }
 async function jsonFetch(url,options={},timeoutMs=8000){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
   const response=await fetch(url,{...options,signal:controller.signal,cache:'no-store'});
   if(!response.ok)throw new Error(await responseError(response));
   if(!(response.headers.get('content-type')||'').includes('application/json'))throw new Error('API вернул HTML вместо JSON. Откройте именно Live Preview сервера, не просмотр файла.');
   return await response.json();
  }catch(e){if(e.name==='AbortError')throw new Error('Сервер не ответил вовремя. Проверьте связь и повторите.');throw e;}
  finally{clearTimeout(timer);}
 }
 const api={SSEParser,responseError,jsonFetch};root.AiraTransport=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
