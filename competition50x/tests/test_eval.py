import hashlib,json
from pathlib import Path
import numpy as np
import pytest
from competition50x.eval import evaluate
from competition50x.data import ROOT


def test_frozen_protocol_and_evaluator():
 seal=json.loads((ROOT/'protocol_frozen.json').read_text());assert seal['elapsed_seconds']<600
 for name,sha in seal['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha


def test_exact_tolerance_boundary():
 y=np.arange(1000)%10;p=y.copy();p[0]=9
 assert evaluate(y,y,p)['quality_pass']
 p[1]=9;assert not evaluate(y,y,p)['quality_pass']


@pytest.mark.parametrize('bad',[np.array([10]),np.array([np.nan]),np.array([]),np.array([[1]])])
def test_reject_invalid_outputs(bad):
 with pytest.raises(ValueError):evaluate(np.array([1]),np.array([1]),bad)


def test_good_accuracy_does_not_override_agreement():
 y=np.arange(1000)%10;b=y.copy();b[:10]=9;p=y.copy()
 assert not evaluate(y,b,p)['quality_pass']
