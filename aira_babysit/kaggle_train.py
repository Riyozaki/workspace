"""Actual LoRA SFT job target, NOT executed/verified on GPU in this sandbox.

Run --check-bundle without torch. Real training requires explicit model revision,
CUDA and the pinned Kaggle dependencies. No successful-training mock/fallback.
"""
from __future__ import annotations
import argparse,hashlib,json,random,re,time,uuid,importlib.metadata
from pathlib import Path
try:
 from .training_data import encode_record,pad_batch
 from .verification import verify
except ImportError:
 from training_data import encode_record,pad_batch
 from verification import verify


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def validate_bundle(root):
 root=Path(root).resolve();manifest=json.loads((root/'manifest.json').read_text())
 if manifest.get('holdout_included') is not False:raise ValueError('Refusing a bundle containing final holdout')
 for name,expected in manifest['files'].items():
  p=(root/name).resolve()
  if not p.is_relative_to(root) or not p.is_file() or sha(p)!=expected:raise ValueError('Bundle file/hash mismatch: '+name)
 train=[json.loads(l) for l in (root/'babysit_train.jsonl').read_text().splitlines()]
 dev=[json.loads(l) for l in (root/'development.jsonl').read_text().splitlines()]
 if not train or not dev:raise ValueError('Empty dataset')
 if {r['family'] for r in train}&{r['family'] for r in dev}:raise ValueError('Training/development family leakage')
 return manifest,train,dev


def run(args):
 manifest,records,dev=validate_bundle(args.bundle)
 if args.check_bundle:
  print(json.dumps({'bundle_valid':True,'train_records':len(records),'development_records':len(dev),'training_executed':False,'gpu_run_verified':False},indent=2));return
 if not args.base_model or not args.base_revision or not re.fullmatch('[a-f0-9]{40}',args.base_revision):raise SystemExit('Real training requires approved --base-model and exact40-hex --base-revision (not main/latest).')
 try:
  import torch
  from transformers import AutoTokenizer,AutoModelForCausalLM
  from peft import LoraConfig,get_peft_model,PeftModel
 except ImportError as exc:raise SystemExit('Training NOT executed: install the explicit Kaggle dependencies first.') from exc
 if not torch.cuda.is_available():raise SystemExit('Training NOT executed: this production target requires a real CUDA worker. No fake CPU success.')
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True);start=time.perf_counter();seed=20261017;random.seed(seed);torch.manual_seed(seed)
 resume_state=None;resume_cp=None
 if args.resume:
  resume_cp=Path(args.resume).resolve()
  if not resume_cp.is_relative_to(out.resolve()):raise ValueError('Resume checkpoint must belong to approved output directory')
  resume_state=json.loads((resume_cp/'resume.json').read_text())
  if resume_state['bundle_manifest_sha256']!=sha(Path(args.bundle)/'manifest.json') or resume_state['base_model']!=args.base_model or resume_state['base_revision']!=args.base_revision:raise ValueError('Resume contract changed')
  if sha(resume_cp/'optimizer.pt')!=resume_state['optimizer_sha256']:raise ValueError('Optimizer checkpoint corrupt')
  for name,expected in resume_state['adapter_files_sha256'].items():
   p=(resume_cp/'adapter'/name).resolve()
   if not p.is_relative_to((resume_cp/'adapter').resolve()) or sha(p)!=expected:raise ValueError('Adapter checkpoint corrupt')
 budget=min(args.budget_seconds,manifest['remaining_active_budget_seconds']);max_steps=min(args.max_steps,manifest['max_train_steps'])
 if budget<60:raise SystemExit('Insufficient remaining budget for setup/train/evaluation/checkpoint reserve.')
 tokenizer=AutoTokenizer.from_pretrained(args.base_model,revision=args.base_revision,trust_remote_code=False)
 if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
 encoded=[encode_record(r,tokenizer,args.context) for r in records]
 dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
 base=AutoModelForCausalLM.from_pretrained(args.base_model,revision=args.base_revision,torch_dtype=dtype,trust_remote_code=False).to('cuda')
 if args.resume:model=PeftModel.from_pretrained(base,str(Path(args.resume)/'adapter'),is_trainable=True)
 else:model=get_peft_model(base,LoraConfig(r=8,lora_alpha=16,lora_dropout=0.,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
 model.config.use_cache=False
 model.enable_input_require_grads();model.gradient_checkpointing_enable()
 params=[p for p in model.parameters() if p.requires_grad];opt=torch.optim.AdamW(params,lr=1e-4)
 use_fp16=dtype==torch.float16;scaler=torch.amp.GradScaler('cuda',enabled=use_fp16);step=0;spent=0.;gradient_verified=False;supervised=0
 bundle_sha=sha(Path(args.bundle)/'manifest.json');plan=random.Random(seed).choices(range(len(encoded)),k=max_steps)
 if resume_state is not None:
  st=resume_state;cp=resume_cp
  saved=torch.load(cp/'optimizer.pt',map_location='cpu',weights_only=True);opt.load_state_dict(saved['optimizer']);scaler.load_state_dict(saved['scaler']);torch.set_rng_state(saved['cpu_rng']);torch.cuda.set_rng_state_all(saved['cuda_rng']);step=st['step'];spent=st['active_seconds'];supervised=st['supervised_target_tokens']
 initial_step=step
 def checkpoint():
  cp=out/f'checkpoint-{step:06d}'
  if cp.exists():
   existing=json.loads((cp/'resume.json').read_text())
   if existing['step']!=step or existing['bundle_manifest_sha256']!=bundle_sha:raise ValueError('Refusing checkpoint overwrite')
   return cp
  temp=out/f'.checkpoint-{step:06d}-{uuid.uuid4().hex}'
  temp.mkdir();model.save_pretrained(temp/'adapter',safe_serialization=True);tokenizer.save_pretrained(temp/'adapter')
  torch.save({'optimizer':opt.state_dict(),'scaler':scaler.state_dict(),'cpu_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all()},temp/'optimizer.pt')
  state={'step':step,'active_seconds':spent+time.perf_counter()-start,'bundle_manifest_sha256':bundle_sha,'base_model':args.base_model,'base_revision':args.base_revision,'optimizer_sha256':sha(temp/'optimizer.pt'),'supervised_target_tokens':supervised,'adapter_files_sha256':{str(p.relative_to(temp/'adapter')):sha(p) for p in (temp/'adapter').rglob('*') if p.is_file()}}
  (temp/'resume.json').write_text(json.dumps(state,indent=2)+'\n');temp.rename(cp)
  pointer=out/'last_checkpoint.tmp';pointer.write_text(json.dumps({'path':str(cp)},indent=2)+'\n');pointer.replace(out/'last_checkpoint.json');return cp
 def evaluate_dev():
  model.eval();results=[];old_cache=model.config.use_cache;model.config.use_cache=True
  try:
   for task in dev:
    if spent+time.perf_counter()-start>=budget:break
    messages=[{'role':'system','content':manifest['serving_system_prompt']}]+task['messages']
    ids=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_tensors='pt').to('cuda')
    with torch.no_grad():gen=model.generate(ids,max_new_tokens=64,do_sample=False,pad_token_id=tokenizer.pad_token_id)
    text=tokenizer.decode(gen[0,ids.shape[1]:],skip_special_tokens=True);results.append({'task_id':task['id'],'answer':text,'verdict':verify(task,text)})
  finally:model.config.use_cache=old_cache
  return results
 baseline_results=evaluate_dev()
 if len(baseline_results)!=len(dev):raise SystemExit('Baseline evaluation exhausted the remaining budget; training NOT executed.')
 model.train();losses=[]
 while step<max_steps and spent+time.perf_counter()-start<budget-45:
  if (out/'PAUSE').exists():break
  row=encoded[plan[step]];batch={k:torch.tensor(v,device='cuda') for k,v in pad_batch([row],tokenizer.pad_token_id).items()}
  opt.zero_grad(set_to_none=True)
  with torch.autocast(device_type='cuda',dtype=dtype):loss=model(**batch).loss
  if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss; refusing candidate')
  scaler.scale(loss).backward();scaler.unscale_(opt)
  norm=torch.nn.utils.clip_grad_norm_(params,1.)
  if not torch.isfinite(norm) or norm.item()==0:raise RuntimeError('Trainable gradient missing/nonfinite; no_grad/frozen-path bug')
  gradient_verified=True;scaler.step(opt);scaler.update();step+=1;losses.append(float(loss.detach()));supervised+=sum(x!=-100 for x in row['labels'])
  if step%25==0:checkpoint()
 if step==0:raise SystemExit('Training NOT executed: setup exhausted budget or no optimizer steps.')
 cp=checkpoint();verdicts=evaluate_dev()
 receipt={'kind':'actual_training_receipt','training_executed':True,'optimizer_steps':step,'optimizer_steps_this_invocation':step-initial_step,'supervised_target_tokens':supervised,'nonzero_gradient_verified':gradient_verified,'active_seconds':spent+time.perf_counter()-start,'budget_seconds':budget,'budget_overrun_seconds':max(0,spent+time.perf_counter()-start-budget),'base_model':args.base_model,'base_revision':args.base_revision,'bundle_manifest_sha256':bundle_sha,'checkpoint':str(cp),'baseline_checkpoint_step':initial_step,'software':{p:importlib.metadata.version(p) for p in ('torch','transformers','peft','safetensors')},'gpu_device':torch.cuda.get_device_name(),'torch_dtype':str(dtype),'context_tokens':args.context,'lora_rank':8,'learning_rate':1e-4,'peak_gpu_allocated_bytes':torch.cuda.max_memory_allocated(),'trainable_parameters':sum(p.numel() for p in params),'baseline_development_results':baseline_results,'development_results':verdicts,'development_nonregression':len(verdicts)==len(dev) and sum(v['verdict']['pass'] for v in verdicts)>=sum(v['verdict']['pass'] for v in baseline_results),'development_complete':len(verdicts)==len(dev),'paused':(out/'PAUSE').exists(),'production_promoted':False,'learning_cycle_complete':False,'next_gate':'independent final holdout plus CPU GGUF/resource evaluation; receipt alone cannot promote','loss_history':losses}
 (out/'training_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--check-bundle',action='store_true');p.add_argument('--base-model');p.add_argument('--base-revision');p.add_argument('--output',default='/kaggle/working/aira_training');p.add_argument('--resume');p.add_argument('--budget-seconds',type=int,default=3600);p.add_argument('--max-steps',type=int,default=100);p.add_argument('--context',type=int,default=512);run(p.parse_args())
