"""Run with python -m aira_babysit --help. No paid/remote teacher calls by default."""
import argparse,json,sys
from pathlib import Path
from .config import DEFAULT_RUNS,RunConfig,ROOT
from .store import Store
from .worker import work


def config_from(args):
 manifest=json.loads((ROOT.parent/'aira_local/model_manifest.json').read_text())
 return RunConfig(budget_seconds=args.budget_seconds,max_examples=args.max_examples,max_new_tokens=args.max_new_tokens,seed=args.seed,teacher=args.teacher,student_url=args.student_url,student_model_sha256=manifest['gguf_sha256'],max_train_steps=args.max_train_steps).validate()


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runs-root',type=Path,default=DEFAULT_RUNS);sub=p.add_subparsers(dest='command',required=True)
 for name in ('create','run'):
  q=sub.add_parser(name);q.add_argument('--budget-seconds',type=int,default=3600);q.add_argument('--max-examples',type=int,default=12);q.add_argument('--max-new-tokens',type=int,default=48);q.add_argument('--max-train-steps',type=int,default=100);q.add_argument('--seed',type=int,default=20261017);q.add_argument('--teacher',choices=['verified_offline','external_required'],default='verified_offline');q.add_argument('--student-url',default='http://127.0.0.1:8000')
 for name in ('work','resume','pause','stop','events'):
  q=sub.add_parser(name);q.add_argument('run_id')
 q=sub.add_parser('status');q.add_argument('run_id',nargs='?')
 sub.add_parser('dashboard').add_argument('--port',type=int,default=8001)
 a=p.parse_args();store=Store(a.runs_root)
 try:
  if a.command in ('create','run'):
   rid=store.create(config_from(a));print(json.dumps({'run_id':rid,'created':True}),flush=True)
   if a.command=='run':result=work(store,rid)
   else:result=store.get(rid)
  elif a.command in ('work','resume'):result=work(store,a.run_id,resume=a.command=='resume')
  elif a.command in ('pause','stop'):store.control(a.run_id,a.command);result=store.get(a.run_id)
  elif a.command=='events':result=store.events(a.run_id)
  elif a.command=='status':result=store.get(a.run_id) if a.run_id else store.list()
  elif a.command=='dashboard':
   import os,uvicorn
   os.environ['AIRA_RUNS_ROOT']=str(store.root);uvicorn.run('aira_babysit.dashboard:app',host='0.0.0.0',port=a.port,access_log=False);return
  print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
 except Exception as exc:
  print(json.dumps({'error':str(exc),'training_executed':False},ensure_ascii=False),file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':main()
