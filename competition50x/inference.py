"""All-support-vector RBF SVC inference; no training labels or cached answers."""
from __future__ import annotations
import ctypes
import time
from pathlib import Path
import numpy as np
from .paths import ART


def coefficients(dual,n_support):
    starts=np.r_[0,np.cumsum(n_support)]
    c=len(n_support);coef=np.zeros((int(starts[-1]),c*(c-1)//2),dtype=np.float64);p=0
    for i in range(c):
        for j in range(i+1,c):
            si=slice(starts[i],starts[i+1]);sj=slice(starts[j],starts[j+1])
            coef[si,p]=dual[j-1,si];coef[sj,p]=dual[i,sj];p+=1
    return coef


def vote(scores,classes):
    if len(classes)==2:
        # Public sklearn binary dual_coef/intercept use positive class 1.
        return classes[(scores[:,0]>0).astype(np.int64)]
    votes=np.zeros((len(scores),len(classes)),dtype=np.int16);p=0
    for i in range(len(classes)):
        for j in range(i+1,len(classes)):
            pos=scores[:,p]>0;votes[:,i]+=pos;votes[:,j]+=~pos;p+=1
    return classes[np.argmax(votes,axis=1)]


def gemm(x,model,block=512,dtype=np.float64,return_scores=False):
    sv=np.asarray(model.support_vectors_,dtype=dtype,order='C');xx=np.asarray(x,dtype=dtype,order='C')
    # Norms/coefficients remain float64 even for float32 dot products.
    svnorm=np.einsum('ij,ij->i',model.support_vectors_,model.support_vectors_)
    xnorm=np.einsum('ij,ij->i',x,x)
    coef=coefficients(model.dual_coef_,model.n_support_);all_scores=[];out=[]
    for start in range(0,len(x),block):
        end=min(start+block,len(x));k=xx[start:end]@sv.T
        # Cast back to float64 before cancellation, exp and all decisions.
        if k.dtype!=np.float64:k=k.astype(np.float64)
        k*=-2.;k+=xnorm[start:end,None];k+=svnorm[None,:]
        k*= -float(model._gamma);np.exp(k,out=k)
        scores=k@coef+model.intercept_
        out.append(vote(scores,model.classes_))
        if return_scores:all_scores.append(scores)
    prediction=np.concatenate(out)
    return (prediction,np.concatenate(all_scores)) if return_scores else prediction


class Compact:
    """Exact integer distances on the original 0..255 pixel alphabet."""
    def __init__(self,path=None,library=None,fused32=False):
        self.fused32=fused32
        with np.load(path or ART/'model_compact.npz',allow_pickle=False) as z:
            self.packed=z['packed'];self.svnorm=z['svnorm'];self.sparse=z['sparse_coef'];self.pairs=z['pair_index'];self.starts=z['starts'];self.intercept=z['intercept'];self.classes=z['classes'];self.gamma=float(z['gamma'])
        if not fused32:
            self.coef=np.zeros((len(self.svnorm),45),dtype=np.float64)
            for cls in range(10):
                self.coef[self.starts[cls]:self.starts[cls+1],self.pairs[cls]]=self.sparse[self.starts[cls]:self.starts[cls+1],:9]
        self.nsv=len(self.svnorm);self.d=784
        self.lib=ctypes.CDLL(str(library or ART/'libu8gemm.so'))
        self.lib.has_vnni.restype=ctypes.c_int
        if not self.lib.has_vnni():raise RuntimeError('Selected compact backend requires AVX512-VNNI')
        self.lib.u8_dot.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
        self.lib.u8_dot.restype=ctypes.c_int
        if fused32:
            self.lib.u8_rbf.argtypes=[ctypes.c_void_p]*4+[ctypes.c_int]*3+[ctypes.c_double]
            self.lib.u8_rbf.restype=ctypes.c_int
            self.lib.mixed_scores.argtypes=[ctypes.c_void_p]*5+[ctypes.c_int]*2
            self.lib.mixed_scores.restype=ctypes.c_int
    def predict(self,x,block=512,return_scores=False):
        if x.dtype!=np.uint8 or x.ndim!=2 or x.shape[1]!=784:raise ValueError('Compact input must be original uint8 pixels')
        x=np.ascontiguousarray(x);pred=[];all_scores=[]
        self.profile={'integer_dot_seconds':0.,'distance_exp_seconds':0.,'decision_vote_seconds':0.}
        for start in range(0,len(x),block):
            xb=x[start:start+block];t0=time.perf_counter()
            if self.fused32:
                k32=np.empty((len(xb),self.nsv),dtype=np.float32)
                code=self.lib.u8_rbf(xb.ctypes.data,self.packed.ctypes.data,self.svnorm.ctypes.data,k32.ctypes.data,len(xb),self.nsv,self.d,self.gamma)
                if code:raise RuntimeError('Fused integer RBF kernel failed: '+str(code))
                self.profile['integer_dot_seconds']+=time.perf_counter()-t0;t0=time.perf_counter()
                # Keep the float32 kernel; native reduction converts each scalar
                # once and accumulates the original coefficients in float64.
                k=k32
            else:
                dot=np.empty((len(xb),self.nsv),dtype=np.int32)
                code=self.lib.u8_dot(xb.ctypes.data,self.packed.ctypes.data,dot.ctypes.data,len(xb),self.nsv,self.d)
                if code:raise RuntimeError('Integer kernel failed: '+str(code))
                self.profile['integer_dot_seconds']+=time.perf_counter()-t0;t0=time.perf_counter()
                q=xb.astype(np.int32);norm=np.einsum('ij,ij->i',q,q,dtype=np.int32)
                dot*=-2;dot+=norm[:,None];dot+=self.svnorm[None,:]
                if dot.min()<0:raise ArithmeticError('Exact integer squared distance is negative')
                k=dot.astype(np.float64);k*=(-self.gamma/65025.);np.exp(k,out=k)
            self.profile['distance_exp_seconds']+=time.perf_counter()-t0;t0=time.perf_counter()
            if self.fused32:
                scores=np.broadcast_to(self.intercept,(len(xb),45)).copy()
                code=self.lib.mixed_scores(k.ctypes.data,self.sparse.ctypes.data,self.starts.ctypes.data,self.pairs.ctypes.data,scores.ctypes.data,len(xb),self.nsv)
                if code:raise RuntimeError('Native float64 decision reduction failed')
            else:scores=k@self.coef+self.intercept
            pred.append(vote(scores,self.classes))
            self.profile['decision_vote_seconds']+=time.perf_counter()-t0
            if return_scores:all_scores.append(scores)
        p=np.concatenate(pred)
        return (p,np.concatenate(all_scores)) if return_scores else p
