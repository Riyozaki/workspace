"""Generate auditable fixed-tile exact-dot / float32-exp VNNI C kernels."""
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parent


def generate(tile=16):
 head='''/* Generated native kernel: uint8 exact dot, optional float32 exp.
   No labels, predictions or workload-dependent constants are embedded.
   D=784 is task input dimensionality; all support vectors are runtime data. */
#include <stdint.h>
#include <string.h>
#include <immintrin.h>
#include <omp.h>
extern __m512 _ZGVeN16v_expf(__m512);
int has_vnni(void) {
 __builtin_cpu_init();
 return __builtin_cpu_supports("avx512vnni") && __builtin_cpu_supports("avx512bw");
}
'''
 pieces=[head]
 for rbf in (False,True):
  name='u8_rbf' if rbf else 'u8_dot'
  if rbf:sig='const uint8_t*x,const int8_t*packed,const int32_t*svnorm,float*out,int nq,int ns,int d,double gamma'
  else:sig='const uint8_t*x,const int8_t*packed,int32_t*out,int nq,int ns,int d'
  s=f'int {name}({sig}) {{\n if(d!=784 || nq<1 || ns<1)return 1;\n const int nb=(ns+15)/16;\n'
  s+=f' #pragma omp parallel for schedule(static) num_threads(2)\n for(int qi=0;qi<nq;qi+={tile}) {{\n'
  s+=f'  uint8_t tail[{tile}*784];const uint8_t*qbase=x+(int64_t)qi*784;\n'
  s+=f'  if(qi+{tile}>nq){{for(int r=0;r<{tile};r++)memcpy(tail+r*784,x+(int64_t)(qi+r<nq?qi+r:qi)*784,784);qbase=tail;}}\n'
  s+=f'  int32_t offset[{tile}],norm[{tile}];\n  for(int r=0;r<{tile};r++){{int32_t a=0,b=0;for(int z=0;z<784;z++){{int32_t v=qbase[r*784+z];a+=v;b+=v*v;}}offset[r]=128*a;norm[r]=b;}}\n'
  s+='  for(int sj=0;sj<nb;sj++){\n'
  s+='   '+','.join('__m512i a0=_mm512_setzero_si512()' if r==0 else f'a{r}=a0' for r in range(tile))+';\n'
  s+='   const int8_t*bp=packed+(int64_t)sj*196*64;\n   for(int k=0;k<196;k++){\n    __m512i b=_mm512_loadu_si512((const void*)(bp+k*64));\n'
  for r in range(tile):
   s+=f'    {{uint32_t v;memcpy(&v,qbase+{r}*784+4*k,4);a{r}=_mm512_dpbusd_epi32(a{r},_mm512_set1_epi32((int)v),b);}}\n'
  s+='   }\n'
  s+=f'   __m512i acc[{tile}]={{'+','.join(f'a{r}' for r in range(tile))+'};\n'
  s+='   int count=ns-sj*16;if(count>16)count=16;__mmask16 mask=(__mmask16)((1u<<count)-1u);\n'
  if rbf:s+='   __m512i sn=_mm512_maskz_loadu_epi32(mask,svnorm+sj*16);\n'
  s+=f'   for(int r=0;r<{tile} && qi+r<nq;r++){{\n    __m512i v=_mm512_add_epi32(acc[r],_mm512_set1_epi32(offset[r]));\n'
  if rbf:
   s+='    __m512i dist=_mm512_sub_epi32(_mm512_add_epi32(sn,_mm512_set1_epi32(norm[r])),_mm512_slli_epi32(v,1));\n'
   s+='    __m512 f=_mm512_mul_ps(_mm512_cvtepi32_ps(dist),_mm512_set1_ps((float)(-gamma/65025.)));\n'
   s+='    __m512 e=_ZGVeN16v_expf(f);_mm512_mask_storeu_ps(out+(int64_t)(qi+r)*ns+sj*16,mask,e);\n'
  else:s+='    _mm512_mask_storeu_epi32(out+(int64_t)(qi+r)*ns+sj*16,mask,v);\n'
  s+='   }\n  }\n }\n return 0;\n}\n'
  pieces.append(s)
 # Mixed float32-kernel / float64-coefficient sparse reductions avoid the
 # O(BS) float64 cast and avoid doing arithmetic on 80% structural zero weights.
 s='''
int mixed_scores(const float*k,const double*coef,const int32_t*starts,
 const int32_t*pairs,double*out,int nq,int ns) {
 if(nq<1 || ns<1)return 1;
 #pragma omp parallel for schedule(static) num_threads(2)
 for(int qi=0;qi<nq;qi+=8) {
  for(int cls=0;cls<10;cls++) {
'''
 s+='   '+','.join('__m512d a0=_mm512_setzero_pd()' if r==0 else f'a{r}=a0' for r in range(16))+';\n'
 s+='   for(int sv=starts[cls];sv<starts[cls+1];sv++){\n    __m512d c0=_mm512_loadu_pd(coef+(int64_t)sv*16);\n    __m512d c1=_mm512_loadu_pd(coef+(int64_t)sv*16+8);\n'
 for r in range(8):
  s+=f'    {{int row=qi+{r}<nq?qi+{r}:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a{2*r}=_mm512_fmadd_pd(f,c0,a{2*r});a{2*r+1}=_mm512_fmadd_pd(f,c1,a{2*r+1});}}\n'
 s+='   }\n   double tmp[8][16];\n'
 for r in range(8):s+=f'   _mm512_storeu_pd(tmp[{r}],a{2*r});_mm512_storeu_pd(tmp[{r}]+8,a{2*r+1});\n'
 s+='''   for(int r=0;r<8 && qi+r<nq;r++) {
    for(int j=0;j<9;j++)out[(int64_t)(qi+r)*45+pairs[cls*9+j]]+=tmp[r][j];
   }
  }
 }
 return 0;
}
'''
 pieces.append(s)
 (ROOT/'u8gemm.c').write_text('\n'.join(pieces))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--tile',type=int,choices=[8,16],default=16);a=p.parse_args();generate(a.tile)
