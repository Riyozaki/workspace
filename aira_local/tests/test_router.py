import json,hashlib
import numpy as np
import pytest
from aira_local.router import BudgetRouter,features,LABELS,ROOT
from aira_local.train_router import load_data


def test_data_split_and_original_negative_result_preserved():
 rows=load_data();families={s:{r['family'] for r in rows if r['split']==s} for s in ('train','development','holdout')}
 assert not families['train']&families['holdout'];assert not families['train']&families['development'];assert not families['holdout']&families['development']
 assert len({r['prompt'] for r in rows})==len(rows)
 manifest=json.loads((ROOT/'data/router_manifest.json').read_text());assert hashlib.sha256((ROOT/'data/router_pilot.jsonl').read_bytes()).hexdigest()==manifest['sha256']
 result=json.loads((ROOT/'results/router_ablation.json').read_text());assert len(result['all_runs'])==6;assert result['deployed_holdout']['accuracy']<.6


def test_feature_determinism_and_no_exact_number_memorization():
 np.testing.assert_array_equal(features(['Посчитай 17+25']),features(['Посчитай 83+19']))
 assert np.isfinite(features(['','привет','What is RAM?'])).all()


@pytest.mark.parametrize('kind',['linear','loop'])
def test_manual_backward_against_finite_difference(kind):
 m=BudgetRouter(kind,7);x=features(['calculate 7+2','hello','search my notes']);y=np.array([1,0,2]);_,g=m.loss_grad(x,y)
 rng=np.random.default_rng(501)
 for key in m.p:
  a=m.p[key]
  for _ in range(3):
   ix=tuple(int(rng.integers(0,d)) for d in a.shape);v=float(a[ix]);eps=.002
   a[ix]=v+eps;plus=m.loss_grad(x,y)[0];a[ix]=v-eps;minus=m.loss_grad(x,y)[0];a[ix]=v
   numeric=(plus-minus)/(2*eps)
   assert np.isclose(numeric,g[key][ix],rtol=.06,atol=7e-4),(kind,key,ix,numeric,g[key][ix])


def test_training_really_changes_weights_and_roundtrip(tmp_path):
 m=BudgetRouter('loop',0);old={k:a.copy() for k,a in m.p.items()};texts=['calculate 2+2','search my notes','hello']*8;labels=['calculator','notes','chat']*8
 x=features(texts);y=np.array([1,2,0]*8);before=m.loss_grad(x,y)[0];m.fit(texts,labels,steps=120);after=m.loss_grad(x,y)[0]
 assert after<before;assert any(not np.array_equal(old[k],m.p[k]) for k in old)
 path=tmp_path/'router.json';m.save(path);q=BudgetRouter.load(path);np.testing.assert_allclose(q.probabilities(texts),m.probabilities(texts))
