"""Generate a per-run Kaggle notebook with the exact bundle checksum.

Notebook code is prepared/contract checked here, NOT GPU executed here.
"""
import json


def notebook(run_id,bundle_sha):
 def code(s):return {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':s.splitlines(True)}
 def md(s):return {'cell_type':'markdown','metadata':{},'source':s.splitlines(True)}
 cells=[md(f'''# AIra Babysit — training handoff {run_id}

**GPU integration NOT yet executed/verified in the Arena sandbox.** This notebook
is an explicit LoRA SFT job target, not proof that training is ready/successful.
Upload the matching bundle as a Kaggle input, enable GPU and internet for setup.
The offline teacher is synthetic/executable, not a connected strong AI API.
A training receipt cannot automatically promote a model to the serving app.
Save Kaggle output/checkpoints explicitly before session loss; /kaggle/working
alone is not durable external storage.
'''),code(f'''import os,sys,time,json,hashlib,glob,zipfile,subprocess,signal
from pathlib import Path
BOOTSTRAP_START=time.monotonic()
EXPECTED_BUNDLE_SHA={bundle_sha!r}
RUN_ID={run_id!r}
BASE_MODEL='HuggingFaceTB/SmolLM2-135M-Instruct'
BASE_REVISION=None  # optionally pre-pin; otherwise resolve ONCE before training
RESUME=None        # checkpoint copied into the run-specific /kaggle/working/aira_training/RUN_ID directory
os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['USE_TF']='0'
'''),code('''candidates=sorted(set(glob.glob('/kaggle/input/**/aira-babysit-*.zip',recursive=True)+glob.glob('/kaggle/input/**/kaggle_bundle.zip',recursive=True)))
if len(candidates)!=1:raise RuntimeError('Select exactly one approved run bundle; do not guess among inputs.')
bundle_file=Path(candidates[0])
if hashlib.sha256(bundle_file.read_bytes()).hexdigest()!=EXPECTED_BUNDLE_SHA:raise RuntimeError('Bundle checksum mismatch')
root=Path('/kaggle/working/aira_bundle');root.mkdir(exist_ok=True)
with zipfile.ZipFile(bundle_file) as z:
 for item in z.infolist():
  target=(root/item.filename).resolve()
  if not target.is_relative_to(root.resolve()) or item.file_size>5_000_000:raise RuntimeError('Unsafe bundle member')
  if item.is_dir():continue
  raw=z.read(item)
  if target.exists() and target.read_bytes()!=raw:raise RuntimeError('Existing bundle differs; use a new output directory')
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
subprocess.check_call([sys.executable,str(root/'kaggle_train.py'),'--bundle',str(root),'--check-bundle'])
manifest=json.loads((root/'manifest.json').read_text())
if manifest['remaining_active_budget_seconds']<60:raise RuntimeError('Not enough budget left; create an approved new run, do not silently extend this one.')
'''),code('''subprocess.check_call([sys.executable,'-m','pip','install','transformers==4.51.3','peft==0.15.2','accelerate==1.6.0','safetensors==0.5.3'])
from huggingface_hub import HfApi
out=Path('/kaggle/working/aira_training')/RUN_ID;out.mkdir(parents=True,exist_ok=True)
approval=out/'training_spec.json'
if approval.exists():
 prior=json.loads(approval.read_text())
 if prior['bundle_sha256']!=EXPECTED_BUNDLE_SHA or prior['base_model']!=BASE_MODEL:raise RuntimeError('Resume specification changed')
 if BASE_REVISION is not None and BASE_REVISION!=prior['base_revision']:raise RuntimeError('Model revision changed')
 BASE_REVISION=prior['base_revision']
else:
 BASE_REVISION=BASE_REVISION or HfApi().model_info(BASE_MODEL).sha
 approval.write_text(json.dumps({'run_id':RUN_ID,'bundle_sha256':EXPECTED_BUNDLE_SHA,'base_model':BASE_MODEL,'base_revision':BASE_REVISION,'resolved_before_training':True},indent=2))
print('Frozen model revision:',BASE_REVISION)
'''),code('''remaining=manifest['remaining_active_budget_seconds']-(time.monotonic()-BOOTSTRAP_START)
if remaining<60:raise RuntimeError('Bootstrap exhausted remaining budget; training not executed')
cmd=[sys.executable,str(root/'kaggle_train.py'),'--bundle',str(root),'--base-model',BASE_MODEL,'--base-revision',BASE_REVISION,'--output',str(out),'--budget-seconds',str(int(remaining)),'--max-steps',str(manifest['max_train_steps'])]
if RESUME:cmd+=['--resume',str(RESUME)]
with (out/'worker.log').open('a') as log:
 proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:rc=proc.wait(timeout=remaining)
 except subprocess.TimeoutExpired:
  os.killpg(proc.pid,signal.SIGTERM)
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
  raise RuntimeError('Budget exhausted; inspect only complete hashed checkpoints. No success claimed.')
if rc:raise RuntimeError('Training worker failed. Read worker.log; no promotion.')
receipt=json.loads((out/'training_receipt.json').read_text());print(json.dumps(receipt,indent=2))
assert receipt['production_promoted'] is False
print('Candidate only. Independent holdout + real CPU resource gate still required.')
'''),md('''## Pause / resume / completion

Create `out / 'PAUSE'` in the printed run-specific output directory to request checkpoint+pause after a
bounded optimizer step. To resume, preserve the complete output directory,
remove PAUSE, set RESUME to a complete checkpoint and re-run with the same frozen
bundle/model recipe. Partial `.checkpoint-*` directories are NOT valid checkpoints.
Never upload secrets into output/logs. Keep final holdout outside the training
bundle. This v0.1 notebook produces a candidate, not an independently accepted or
automatically deployed new language model. Full repeated learning cycles and the
external strong-teacher adapter remain separate integration gates.
''')]
 for i,cell in enumerate(cells):cell['id']=f'aira-{run_id}-{i:02d}'
 return {'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'aira':{'run_id':run_id,'training_executed_in_sandbox':False,'bundle_sha256':bundle_sha}},'nbformat':4,'nbformat_minor':5}
