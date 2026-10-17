"""Executed engineering probes against the real web API, not an LM benchmark."""
import argparse,json,time,platform,os,importlib.metadata
from datetime import datetime,timezone
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parent


def main(output_dir=None):
 out=Path(output_dir) if output_dir else ROOT.parent/'artifacts/aira_local/runtime_probes'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
 out.mkdir(parents=True,exist_ok=True)
 client=httpx.Client(base_url='http://127.0.0.1:8000',timeout=60.)
 start=client.get('/api/status').json();t=time.perf_counter();time.sleep(3.)
 idle=client.get('/api/status').json();idle_seconds=time.perf_counter()-t
 records=[]
 cases=[('model','Explain what a CPU does in one sentence.'),('model','What is the capital of France? Answer briefly.'),('model','Reply with exactly the word ready.'),('model','Привет! Кто ты?'),('calculator','Посчитай (18+7)*4'),('notes','Найди в заметках план обучения')]
 for mode,text in cases:
  t=time.perf_counter();r=client.post('/api/chat',json={'messages':[{'role':'user','content':text}],'mode':mode,'max_tokens':48,'notes':[{'id':'training','title':'План обучения','text':'Большое обучение позже на Kaggle. Сейчас проверяется локальный прототип.'}]});wall=time.perf_counter()-t
  if r.status_code!=200:raise RuntimeError(r.text)
  events=[json.loads(line[6:]) for line in r.text.splitlines() if line.startswith('data: ')]
  done=events[-1];assert done['type']=='done';assert done['metrics']['error'] is None
  answer=''.join(e.get('text','') for e in events if e['type']=='token')
  records.append({'mode':mode,'prompt':text,'answer':answer,'client_http_wall_seconds':wall,'metrics':done['metrics'],'judgment':'not independently scored; raw answer preserved'})
 end=client.get('/api/status').json()
 report={'observed_utc':datetime.now(timezone.utc).isoformat(),'scope':'Engineering API probes. Same available public pretrained model. Not an independent language/agent benchmark, not a speedup comparison.','idle_window_seconds':idle_seconds,'idle_sample_interrupted':start['last_request']!=idle['last_request'],'idle_process_rss_bytes':idle['telemetry']['rss_bytes'],'idle_sampled_cpu_percent_total_capacity':idle['telemetry']['cpu_percent_total_capacity'],'peak_sampled_process_rss_bytes':end['telemetry']['peak_sampled_rss_bytes'],'native_inference_threads':1,'logical_cpu_affinity':sorted(os.sched_getaffinity(0)),'gpu_layers':0,'energy_joules':None,'raw_cases':records,'privacy_metrics_no_answer_text':all('text' not in r['metrics']['model_metrics'] for r in records)}
 (out/'runtime_api_probes.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 env={'python':platform.python_version(),'platform':platform.platform(),'affinity':sorted(os.sched_getaffinity(0)),'memory_total_bytes':end['telemetry']['system_memory_bytes'],'versions':{p:importlib.metadata.version(p) for p in ('numpy','fastapi','uvicorn','psutil','httpx','pytest','llama-cpp-python')},'native_runtime':end['model']['runtime_system_info'],'preview_scope':'Arena backend CPU, not browser inference or target-device validation'}
 (out/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
 print(json.dumps({'idle_rss_mib':report['idle_process_rss_bytes']/1048576,'peak_rss_mib':report['peak_sampled_process_rss_bytes']/1048576,'all_real_requests_completed':True,'cases':[{'mode':r['mode'],'answer':r['answer'],'client_seconds':r['client_http_wall_seconds'],'tokens':r['metrics']['generated_tokens']} for r in records]},indent=2,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path);a=p.parse_args();main(a.output_dir)
