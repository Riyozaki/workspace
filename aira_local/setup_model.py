"""Obtain an Apache-2.0 pretrained model via a pinned PyPI distribution.

Extract DATA ONLY: the llm-smollm2 plugin is not imported or installed.
No model files or large wheels are added to Git. No network during inference.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ART=ROOT.parent/'artifacts/aira_local'
MODEL=ART/'models/SmolLM2-135M-Instruct.Q4_1.gguf'
WHEEL_URL='https://files.pythonhosted.org/packages/06/be/9df8343f073e455d94f4acda2c211e84dec4d2879ee959c8dfbaa40d7d1b/llm_smollm2-0.1.2-py3-none-any.whl'
WHEEL_SHA='bcc81830d10ce7d9e76640cad826a4b79ed3e4547c78a0be5c4f2fb0e2448c70'
MEMBER='llm_smollm2/SmolLM2-135M-Instruct.Q4_1.gguf'


def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()


def main(output_model=None):
 target=Path(output_model).resolve() if output_model else MODEL
 target.parent.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True);manifest=ROOT/'model_manifest.json'
 if target.exists() and manifest.exists():
  expected=json.loads(manifest.read_text())['gguf_sha256']
  if digest(target)==expected:print('Verified existing model:',target);return
 t=time.perf_counter();wheel=ART/'llm-smollm2-0.1.2.whl';tmp=wheel.with_suffix('.partial')
 print('Downloading pinned 92.9MB distribution from PyPI...',flush=True)
 with urllib.request.urlopen(WHEEL_URL,timeout=120) as response,tmp.open('wb') as f:shutil.copyfileobj(response,f,1024*1024)
 if digest(tmp)!=WHEEL_SHA:raise RuntimeError('Distribution SHA-256 mismatch')
 tmp.replace(wheel)
 with zipfile.ZipFile(wheel) as archive:
  info=archive.getinfo(MEMBER)
  if info.file_size>250_000_000:raise RuntimeError('Unexpected model size')
  with archive.open(MEMBER) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
 if target.read_bytes()[:4]!=b'GGUF':raise RuntimeError('Invalid GGUF header')
 record={'model_id':'HuggingFaceTB/SmolLM2-135M-Instruct','parameters_nominal':135000000,'quantization':'Q4_1','license':'Apache-2.0','distribution':'llm-smollm2==0.1.2','publisher_repository':'https://github.com/simonw/llm-smollm2','upstream_quantized_revision':'QuantFactory/SmolLM2-135M-Instruct-GGUF@ab810cf68114990406fdf996510dd3d3c6adbdf5','download_url':WHEEL_URL,'distribution_sha256':WHEEL_SHA,'gguf_sha256':digest(target),'gguf_bytes':target.stat().st_size,'setup_seconds':time.perf_counter()-t,'role':'Unmodified pretrained control model; NOT an AIra-trained language model','runtime_network_required':False}
 if manifest.exists():
  expected=json.loads(manifest.read_text())
  if record['gguf_sha256']!=expected['gguf_sha256']:raise RuntimeError('Downloaded GGUF differs from published model manifest')
  # Preserve published measurements; record this setup run outside Git.
  (ART/'setup_run.json').write_text(json.dumps(record,indent=2)+'\n')
 else:manifest.write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record,indent=2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-model',type=Path);a=p.parse_args();main(a.output_model)
