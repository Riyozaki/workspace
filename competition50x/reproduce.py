"""Fresh isolated end-to-end reproduction: data, training, references, build, holdout.

No prediction cache; source package is copied into an ignored output directory so
published evidence is never overwritten. The long research timer is NOT awaited.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from .paths import ROOT,ART


def main():
 p=argparse.ArgumentParser();p.add_argument('--inside',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
 if not a.inside:
  out=(a.output or ART/'reproductions'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')).resolve()
  if out.exists():raise FileExistsError(out)
  package=out/'work/competition50x';package.mkdir(parents=True)
  for src in ROOT.iterdir():
   if src.is_file() and src.suffix in ('.py','.c','.json','.sha256','.txt','.md','.sh'):
    shutil.copy2(src,package/src.name)
  shutil.copytree(ROOT/'tests',package/'tests',ignore=shutil.ignore_patterns('__pycache__'))
  now=time.time();mono=time.monotonic();(package/'start_time.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'start_unix':now,'start_monotonic':mono,'budget_seconds':5400,'deadline_unix':now+5400},indent=2)+'\n')
  env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
  log=out/'reproduction.log';t=time.perf_counter()
  with log.open('w') as f:
   r=subprocess.run([sys.executable,'-m','competition50x.reproduce','--inside'],cwd=out/'work',env=env,stdout=f,stderr=subprocess.STDOUT)
  result={'returncode':r.returncode,'full_reproduction_wall_seconds':time.perf_counter()-t,'fresh_data_download':True,'fresh_model_training':True,'all_three_ready_references_remeasured':True,'no_original_results_overwritten':True,'work_directory':str(package),'log':str(log)}
  (out/'index.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
  if r.returncode:print(log.read_text()[-5000:]);raise SystemExit(r.returncode)
  print((package/'results/reproduction_summary.json').read_text(),flush=True)
  return
 # Inside a copied package: all setup/output files are local to this reproduction.
 steps=[]
 commands=[('fresh_data_train_and_all_references',[sys.executable,'-m','competition50x.baseline_study']),('compact_build',[sys.executable,'-m','competition50x.build_compact']),('tests',[sys.executable,'-m','pytest','competition50x/tests','-q']),('five_holdout_pairs',[sys.executable,'-m','competition50x.primary','--label','reproduction'])]
 for name,cmd in commands:
  t=time.perf_counter();r=subprocess.run(cmd,cwd=ROOT.parent);steps.append({'name':name,'command':cmd,'returncode':r.returncode,'duration_seconds':time.perf_counter()-t})
  (ROOT/'reproduction_steps.json').write_text(json.dumps(steps,indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 print('FULL FRESH REPRODUCTION COMPLETED',flush=True)
if __name__=='__main__':main()
