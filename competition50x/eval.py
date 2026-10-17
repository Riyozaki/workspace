"""Frozen evaluator: CLI scores saved predictions; never imports candidate code."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np

ACCURACY_TOLERANCE=0.001
MIN_LABEL_AGREEMENT=0.999

def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def evaluate(y,baseline,candidate):
 y=np.asarray(y);baseline=np.asarray(baseline);candidate=np.asarray(candidate)
 if y.ndim!=1 or baseline.shape!=y.shape or candidate.shape!=y.shape or not len(y):raise ValueError('Prediction/target shapes must be equal nonempty vectors')
 for a in (y,baseline,candidate):
  if not np.isfinite(a).all() or not np.isin(a,np.arange(10)).all():raise ValueError('Invalid Fashion-MNIST class labels')
 ba=float(np.mean(baseline==y));ca=float(np.mean(candidate==y));agreement=float(np.mean(candidate==baseline))
 return {'n':len(y),'baseline_accuracy':ba,'candidate_accuracy':ca,'accuracy_drop_absolute':ba-ca,'accuracy_tolerance_absolute':ACCURACY_TOLERANCE,'label_agreement':agreement,'min_label_agreement':MIN_LABEL_AGREEMENT,'quality_pass':bool(ca>=ba-ACCURACY_TOLERANCE-1e-15 and agreement>=MIN_LABEL_AGREEMENT-1e-15)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--labels',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=evaluate(np.load(a.labels,allow_pickle=False),np.load(a.baseline,allow_pickle=False),np.load(a.candidate,allow_pickle=False));r['sha256']={n:sha256(getattr(a,n)) for n in ('labels','baseline','candidate')}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
