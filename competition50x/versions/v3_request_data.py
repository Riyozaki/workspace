"""Same IDX decoding/normalization as frozen data.py, without downloader imports."""
import gzip,struct
from pathlib import Path
import numpy as np
from .paths import ROOT,ART,DATA


def images(path):
 raw=gzip.decompress(Path(path).read_bytes());magic,n,h,w=struct.unpack('>IIII',raw[:16])
 if magic!=2051 or (h,w)!=(28,28) or len(raw)!=16+n*h*w:raise ValueError('Invalid IDX images')
 return np.frombuffer(raw,dtype=np.uint8,offset=16).reshape(n,784)


def labels(path):
 raw=gzip.decompress(Path(path).read_bytes());magic,n=struct.unpack('>II',raw[:8])
 if magic!=2049 or len(raw)!=8+n:raise ValueError('Invalid IDX labels')
 return np.frombuffer(raw,dtype=np.uint8,offset=8)


def load_split(split):
 if split not in ('validation','holdout'):raise ValueError(split)
 with np.load(ART/'splits.npz',allow_pickle=False) as z:idx=z[split]
 x=images(DATA/'t10k-images-idx3-ubyte.gz')[idx].astype(np.float64)/255.
 y=labels(DATA/'t10k-labels-idx1-ubyte.gz')[idx]
 return x,y
