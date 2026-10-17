"""Pinned real Fashion-MNIST; no generated/duplicated workloads."""
from __future__ import annotations
import base64,gzip,hashlib,json,struct,urllib.request
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
ART=ROOT/'artifacts';DATA=ART/'data'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def api(url):
 return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'reproducible-ml-research'}),timeout=120))

def download():
 DATA.mkdir(parents=True,exist_ok=True)
 source=json.loads((ROOT/'source_commit.json').read_text());commit=source['commit']
 manifest=ROOT/'data_manifest.json'
 if manifest.exists():
  records=json.loads(manifest.read_text())['files']
  if all((DATA/r['name']).exists() and digest(DATA/r['name'])==r['sha256'] for r in records):return
 tree=api(f'https://api.github.com/repos/{source["repo"]}/git/trees/{commit}?recursive=1')['tree']
 names=['train-images-idx3-ubyte.gz','train-labels-idx1-ubyte.gz','t10k-images-idx3-ubyte.gz','t10k-labels-idx1-ubyte.gz']
 records=[]
 for name in names:
  ent=next(r for r in tree if r['path']=='data/fashion/'+name)
  blob=api(ent['url']);raw=base64.b64decode(blob['content'])
  actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  if actual!=ent['sha']:raise ValueError('Git blob mismatch')
  (DATA/name).write_bytes(raw);records.append({'name':name,'git_blob_sha1':actual,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'api':ent['url']})
  print('Downloaded',name,len(raw),flush=True)
 manifest.write_text(json.dumps({'repo':source['repo'],'commit':commit,'files':records},indent=2)+'\n')

def images(path):
 raw=gzip.decompress(Path(path).read_bytes());magic,n,h,w=struct.unpack('>IIII',raw[:16])
 if magic!=2051 or (h,w)!=(28,28) or len(raw)!=16+n*h*w:raise ValueError('Invalid IDX images')
 return np.frombuffer(raw,dtype=np.uint8,offset=16).reshape(n,784)

def labels(path):
 raw=gzip.decompress(Path(path).read_bytes());magic,n=struct.unpack('>II',raw[:8])
 if magic!=2049 or len(raw)!=8+n:raise ValueError('Invalid IDX labels')
 return np.frombuffer(raw,dtype=np.uint8,offset=8)

def create_splits():
 from sklearn.model_selection import train_test_split
 y=labels(DATA/'t10k-labels-idx1-ubyte.gz');idx=np.arange(len(y))
 val,holdout=train_test_split(idx,test_size=.5,stratify=y,random_state=20261017)
 np.savez(ART/'splits.npz',validation=val,holdout=holdout)
 (ROOT/'split_manifest.json').write_text(json.dumps({'seed':20261017,'train_n':60000,'validation_n':len(val),'holdout_n':len(holdout),'indices_sha256':digest(ART/'splits.npz'),'disjoint':not bool(set(val)&set(holdout))},indent=2)+'\n')

def load_split(split):
 if split not in ('validation','holdout'):raise ValueError(split)
 with np.load(ART/'splits.npz',allow_pickle=False) as z:idx=z[split]
 x=images(DATA/'t10k-images-idx3-ubyte.gz')[idx].astype(np.float64)/255.
 y=labels(DATA/'t10k-labels-idx1-ubyte.gz')[idx]
 return x,y
