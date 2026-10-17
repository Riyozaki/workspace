"""Tiny learned budget router, NOT a language model.

Linear control and a shared-weight iterative tanh MLP; explicit NumPy backward.
No answers or tool expressions are stored in learned weights. Uncertain inputs
abstain to the actual pretrained language model.
"""
from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
import numpy as np

LABELS=('chat','calculator','notes')
DIM=512
ROOT=Path(__file__).resolve().parent


def features(texts):
 x=np.zeros((len(texts),DIM),dtype=np.float32)
 for row,text in enumerate(texts):
  t=' '+re.sub(r'\d+(?:[.,]\d+)?','0',str(text).casefold().strip())[:700]+' '
  for n in (2,3,4):
   for i in range(max(0,len(t)-n+1)):
    h=hashlib.blake2b(t[i:i+n].encode(),digest_size=4,person=b'AIraRout').digest();v=int.from_bytes(h,'little')
    x[row,v%DIM]+=1. if v&0x80000000 else -1.
  norm=float(np.linalg.norm(x[row]));x[row]/=max(norm,1.)
 return x


def softmax(z):
 e=np.exp(z-z.max(axis=1,keepdims=True));return e/e.sum(axis=1,keepdims=True)


class BudgetRouter:
 def __init__(self,kind='linear',seed=0,threshold=.9,params=None):
  if kind not in ('linear','loop'):raise ValueError(kind)
  self.kind=kind;self.seed=seed;self.threshold=threshold;r=np.random.default_rng(seed)
  if params is not None:self.p={k:np.asarray(v,dtype=np.float32) for k,v in params.items()}
  elif kind=='linear':self.p={'w':r.normal(0,.03,(DIM,3)).astype(np.float32),'b':np.zeros(3,dtype=np.float32)}
  else:self.p={'w':r.normal(0,.07,(DIM,24)).astype(np.float32),'b':np.zeros(24,dtype=np.float32),'r':r.normal(0,.02,(24,24)).astype(np.float32),'c':np.zeros(24,dtype=np.float32),'o':r.normal(0,.07,(24,3)).astype(np.float32),'d':np.zeros(3,dtype=np.float32)}
 @property
 def parameters(self):return sum(a.size for a in self.p.values())
 def forward(self,x,cache=False):
  p=self.p
  if self.kind=='linear':return x@p['w']+p['b'],None
  h0=np.tanh(x@p['w']+p['b']);h=h0;states=[]
  for _ in range(2):
   prev=h;h=np.tanh(prev+.35*(prev@p['r']+p['c']));states.append((prev,h))
  return h@p['o']+p['d'],(h0,states,h)
 def loss_grad(self,x,y,l2=.001):
  z,c=self.forward(x,True);prob=softmax(z);n=len(y)
  loss=float(-np.log(np.maximum(prob[np.arange(n),y],1e-12)).mean())
  dz=prob.copy();dz[np.arange(n),y]-=1.;dz/=n;p=self.p
  if self.kind=='linear':g={'w':x.T@dz,'b':dz.sum(0)}
  else:
   h0,states,h=c;g={'o':h.T@dz,'d':dz.sum(0),'r':np.zeros_like(p['r']),'c':np.zeros_like(p['c'])};dh=dz@p['o'].T
   for prev,out in reversed(states):
    da=dh*(1-out*out);g['r']+=.35*(prev.T@da);g['c']+=.35*da.sum(0);dh=da+.35*(da@p['r'].T)
   da=dh*(1-h0*h0);g.update(w=x.T@da,b=da.sum(0))
  for k in p:
   if p[k].ndim>1:loss+=.5*l2*float(np.square(p[k]).sum());g[k]+=l2*p[k]
  return loss,g
 def fit(self,texts,targets,steps=450,batch=32,lr=.015):
  x=features(texts);y=np.array([LABELS.index(t) for t in targets]);rng=np.random.default_rng(self.seed+104)
  m={k:np.zeros_like(v) for k,v in self.p.items()};v={k:np.zeros_like(a) for k,a in self.p.items()};t0=time.perf_counter()
  for step in range(1,steps+1):
   idx=rng.integers(0,len(y),min(batch,len(y)));loss,g=self.loss_grad(x[idx],y[idx]);gn=np.sqrt(sum(float(np.square(a).sum()) for a in g.values()));scale=min(1.,5./max(gn,1e-8))
   for k in self.p:
    a=g[k]*scale;m[k]=.9*m[k]+.1*a;v[k]=.999*v[k]+.001*a*a
    self.p[k]-=lr*(m[k]/(1-.9**step))/(np.sqrt(v[k]/(1-.999**step))+1e-8)
  return {'steps':steps,'train_seconds':time.perf_counter()-t0,'last_batch_loss':loss,'parameters':self.parameters,'kind':self.kind,'seed':self.seed}
 def probabilities(self,texts):return softmax(self.forward(features(texts))[0])
 def route(self,text):
  t=time.perf_counter();p=self.probabilities([text])[0];i=int(p.argmax());score=float(p[i]);intent=LABELS[i]
  accepted=intent!='chat' and score>=self.threshold
  return {'predicted':intent,'selected':intent if accepted else 'chat','score':score,'threshold':self.threshold,'accepted_fast_path':accepted,'scores':{l:float(p[j]) for j,l in enumerate(LABELS)},'elapsed_ms':1000*(time.perf_counter()-t),'kind':self.kind,'parameters':self.parameters,'score_is_calibrated_probability':False}
 def save(self,path,metadata=None):
  Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps({'kind':self.kind,'seed':self.seed,'threshold':self.threshold,'dimension':DIM,'labels':LABELS,'params':{k:v.tolist() for k,v in self.p.items()},'metadata':metadata or {}},ensure_ascii=False,separators=(',',':'))+'\n')
 @classmethod
 def load(cls,path):
  d=json.loads(Path(path).read_text());return cls(d['kind'],d['seed'],d['threshold'],d['params'])


def metrics(model,rows):
 probs=model.probabilities([r['prompt'] for r in rows]);truth=np.array([LABELS.index(r['target']) for r in rows]);pred=probs.argmax(1);score=probs.max(1);accepted=(pred!=0)&(score>=model.threshold)
 f=[]
 for k in range(3):
  tp=np.sum((pred==k)&(truth==k));fp=np.sum((pred==k)&(truth!=k));fn=np.sum((pred!=k)&(truth==k));f.append(float(2*tp/max(1,2*tp+fp+fn)))
 return {'n':len(rows),'accuracy':float((pred==truth).mean()),'macro_f1':float(np.mean(f)),'fast_path_coverage':float(accepted.mean()),'fast_path_precision':float((pred[accepted]==truth[accepted]).mean()) if accepted.any() else None,'wrong_fast_paths':int(np.sum(accepted&(pred!=truth))),'threshold':model.threshold,'parameters':model.parameters}


def calibrate(model,rows):
 best=1.0001;coverage=0.
 for t in (.6,.7,.8,.85,.9,.95,.98,.995):
  model.threshold=t;m=metrics(model,rows)
  if m['fast_path_precision'] is not None and m['fast_path_precision']>=.98 and m['fast_path_coverage']>coverage:best=t;coverage=m['fast_path_coverage']
 model.threshold=best;return metrics(model,rows)
