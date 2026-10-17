from __future__ import annotations
from dataclasses import asdict,dataclass
import hashlib,json,re
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
DEFAULT_RUNS=ROOT.parent/'artifacts/aira_babysit'


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def safe_id(value):
 if not re.fullmatch(r'[a-f0-9]{16}',value):raise ValueError('Invalid run ID')
 return value


@dataclass(frozen=True)
class RunConfig:
 budget_seconds:int=3600
 max_examples:int=12
 max_new_tokens:int=48
 seed:int=20261017
 teacher:str='verified_offline'
 student_url:str='http://127.0.0.1:8000'
 student_model_sha256:str=''
 max_train_steps:int=100
 training_backend:str='kaggle_handoff'
 checkpoint_every:int=1
 def validate(self):
  if not 5<=self.budget_seconds<=7200:raise ValueError('Budget must be5..7200 seconds')
  if not 1<=self.max_examples<=1000:raise ValueError('Examples must be1..1000')
  if not 8<=self.max_new_tokens<=96:raise ValueError('Output must be8..96tokens')
  if self.teacher not in ('verified_offline','external_required'):raise ValueError('Unsupported teacher')
  if self.training_backend!='kaggle_handoff':raise ValueError('No local GGUF SFT backend is available; do not fake training')
  if not 1<=self.max_train_steps<=1000:raise ValueError('Training step budget must be1..1000')
  parsed=urlparse(self.student_url)
  if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username is not None or parsed.password is not None or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.port is None or not 1<=parsed.port<=65535:raise ValueError('This prototype only calls its approved loopback student API')
  if not self.student_model_sha256:raise ValueError('Freeze an explicit student model SHA before the run')
  if not re.fullmatch('[a-f0-9]{64}',self.student_model_sha256):raise ValueError('Invalid model SHA')
  return self
 def to_dict(self):return asdict(self)


def frozen_sources():
 return {**{name:digest(ROOT/name) for name in ('tasks.py','verification.py','training_data.py','kaggle_train.py','worker.py','store.py','config.py','notebook.py')},'serving_engine.py':digest(ROOT.parent/'aira_local/engine.py')}
