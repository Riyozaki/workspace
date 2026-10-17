/* Generated native kernel: uint8 exact dot, optional float32 exp.
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

int u8_dot(const uint8_t*x,const int8_t*packed,int32_t*out,int nq,int ns,int d) {
 if(d!=784 || nq<1 || ns<1)return 1;
 const int nb=(ns+15)/16;
 #pragma omp parallel for schedule(static) num_threads(2)
 for(int qi=0;qi<nq;qi+=8) {
  uint8_t tail[8*784];const uint8_t*qbase=x+(int64_t)qi*784;
  if(qi+8>nq){for(int r=0;r<8;r++)memcpy(tail+r*784,x+(int64_t)(qi+r<nq?qi+r:qi)*784,784);qbase=tail;}
  int32_t offset[8],norm[8];
  for(int r=0;r<8;r++){int32_t a=0,b=0;for(int z=0;z<784;z++){int32_t v=qbase[r*784+z];a+=v;b+=v*v;}offset[r]=128*a;norm[r]=b;}
  for(int sj=0;sj<nb;sj++){
   __m512i a0=_mm512_setzero_si512(),a1=a0,a2=a0,a3=a0,a4=a0,a5=a0,a6=a0,a7=a0;
   const int8_t*bp=packed+(int64_t)sj*196*64;
   for(int k=0;k<196;k++){
    __m512i b=_mm512_loadu_si512((const void*)(bp+k*64));
    {uint32_t v;memcpy(&v,qbase+0*784+4*k,4);a0=_mm512_dpbusd_epi32(a0,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+1*784+4*k,4);a1=_mm512_dpbusd_epi32(a1,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+2*784+4*k,4);a2=_mm512_dpbusd_epi32(a2,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+3*784+4*k,4);a3=_mm512_dpbusd_epi32(a3,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+4*784+4*k,4);a4=_mm512_dpbusd_epi32(a4,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+5*784+4*k,4);a5=_mm512_dpbusd_epi32(a5,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+6*784+4*k,4);a6=_mm512_dpbusd_epi32(a6,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+7*784+4*k,4);a7=_mm512_dpbusd_epi32(a7,_mm512_set1_epi32((int)v),b);}
   }
   __m512i acc[8]={a0,a1,a2,a3,a4,a5,a6,a7};
   int count=ns-sj*16;if(count>16)count=16;__mmask16 mask=(__mmask16)((1u<<count)-1u);
   for(int r=0;r<8 && qi+r<nq;r++){
    __m512i v=_mm512_add_epi32(acc[r],_mm512_set1_epi32(offset[r]));
    _mm512_mask_storeu_epi32(out+(int64_t)(qi+r)*ns+sj*16,mask,v);
   }
  }
 }
 return 0;
}

int u8_rbf(const uint8_t*x,const int8_t*packed,const int32_t*svnorm,float*out,int nq,int ns,int d,double gamma) {
 if(d!=784 || nq<1 || ns<1)return 1;
 const int nb=(ns+15)/16;
 #pragma omp parallel for schedule(static) num_threads(2)
 for(int qi=0;qi<nq;qi+=8) {
  uint8_t tail[8*784];const uint8_t*qbase=x+(int64_t)qi*784;
  if(qi+8>nq){for(int r=0;r<8;r++)memcpy(tail+r*784,x+(int64_t)(qi+r<nq?qi+r:qi)*784,784);qbase=tail;}
  int32_t offset[8],norm[8];
  for(int r=0;r<8;r++){int32_t a=0,b=0;for(int z=0;z<784;z++){int32_t v=qbase[r*784+z];a+=v;b+=v*v;}offset[r]=128*a;norm[r]=b;}
  for(int sj=0;sj<nb;sj++){
   __m512i a0=_mm512_setzero_si512(),a1=a0,a2=a0,a3=a0,a4=a0,a5=a0,a6=a0,a7=a0;
   const int8_t*bp=packed+(int64_t)sj*196*64;
   for(int k=0;k<196;k++){
    __m512i b=_mm512_loadu_si512((const void*)(bp+k*64));
    {uint32_t v;memcpy(&v,qbase+0*784+4*k,4);a0=_mm512_dpbusd_epi32(a0,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+1*784+4*k,4);a1=_mm512_dpbusd_epi32(a1,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+2*784+4*k,4);a2=_mm512_dpbusd_epi32(a2,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+3*784+4*k,4);a3=_mm512_dpbusd_epi32(a3,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+4*784+4*k,4);a4=_mm512_dpbusd_epi32(a4,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+5*784+4*k,4);a5=_mm512_dpbusd_epi32(a5,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+6*784+4*k,4);a6=_mm512_dpbusd_epi32(a6,_mm512_set1_epi32((int)v),b);}
    {uint32_t v;memcpy(&v,qbase+7*784+4*k,4);a7=_mm512_dpbusd_epi32(a7,_mm512_set1_epi32((int)v),b);}
   }
   __m512i acc[8]={a0,a1,a2,a3,a4,a5,a6,a7};
   int count=ns-sj*16;if(count>16)count=16;__mmask16 mask=(__mmask16)((1u<<count)-1u);
   __m512i sn=_mm512_maskz_loadu_epi32(mask,svnorm+sj*16);
   for(int r=0;r<8 && qi+r<nq;r++){
    __m512i v=_mm512_add_epi32(acc[r],_mm512_set1_epi32(offset[r]));
    __m512i dist=_mm512_sub_epi32(_mm512_add_epi32(sn,_mm512_set1_epi32(norm[r])),_mm512_slli_epi32(v,1));
    __m512 f=_mm512_mul_ps(_mm512_cvtepi32_ps(dist),_mm512_set1_ps((float)(-gamma/65025.)));
    __m512 e=_ZGVeN16v_expf(f);_mm512_mask_storeu_ps(out+(int64_t)(qi+r)*ns+sj*16,mask,e);
   }
  }
 }
 return 0;
}


int mixed_scores(const float*k,const double*coef,const int32_t*starts,
 const int32_t*pairs,double*out,int nq,int ns) {
 if(nq<1 || ns<1)return 1;
 #pragma omp parallel for schedule(static) num_threads(2)
 for(int qi=0;qi<nq;qi+=8) {
  for(int cls=0;cls<10;cls++) {
   __m512d a0=_mm512_setzero_pd(),a1=a0,a2=a0,a3=a0,a4=a0,a5=a0,a6=a0,a7=a0,a8=a0,a9=a0,a10=a0,a11=a0,a12=a0,a13=a0,a14=a0,a15=a0;
   for(int sv=starts[cls];sv<starts[cls+1];sv++){
    __m512d c0=_mm512_loadu_pd(coef+(int64_t)sv*16);
    __m512d c1=_mm512_loadu_pd(coef+(int64_t)sv*16+8);
    {int row=qi+0<nq?qi+0:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a0=_mm512_fmadd_pd(f,c0,a0);a1=_mm512_fmadd_pd(f,c1,a1);}
    {int row=qi+1<nq?qi+1:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a2=_mm512_fmadd_pd(f,c0,a2);a3=_mm512_fmadd_pd(f,c1,a3);}
    {int row=qi+2<nq?qi+2:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a4=_mm512_fmadd_pd(f,c0,a4);a5=_mm512_fmadd_pd(f,c1,a5);}
    {int row=qi+3<nq?qi+3:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a6=_mm512_fmadd_pd(f,c0,a6);a7=_mm512_fmadd_pd(f,c1,a7);}
    {int row=qi+4<nq?qi+4:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a8=_mm512_fmadd_pd(f,c0,a8);a9=_mm512_fmadd_pd(f,c1,a9);}
    {int row=qi+5<nq?qi+5:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a10=_mm512_fmadd_pd(f,c0,a10);a11=_mm512_fmadd_pd(f,c1,a11);}
    {int row=qi+6<nq?qi+6:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a12=_mm512_fmadd_pd(f,c0,a12);a13=_mm512_fmadd_pd(f,c1,a13);}
    {int row=qi+7<nq?qi+7:qi;__m512d f=_mm512_set1_pd((double)k[(int64_t)row*ns+sv]);a14=_mm512_fmadd_pd(f,c0,a14);a15=_mm512_fmadd_pd(f,c1,a15);}
   }
   double tmp[8][16];
   _mm512_storeu_pd(tmp[0],a0);_mm512_storeu_pd(tmp[0]+8,a1);
   _mm512_storeu_pd(tmp[1],a2);_mm512_storeu_pd(tmp[1]+8,a3);
   _mm512_storeu_pd(tmp[2],a4);_mm512_storeu_pd(tmp[2]+8,a5);
   _mm512_storeu_pd(tmp[3],a6);_mm512_storeu_pd(tmp[3]+8,a7);
   _mm512_storeu_pd(tmp[4],a8);_mm512_storeu_pd(tmp[4]+8,a9);
   _mm512_storeu_pd(tmp[5],a10);_mm512_storeu_pd(tmp[5]+8,a11);
   _mm512_storeu_pd(tmp[6],a12);_mm512_storeu_pd(tmp[6]+8,a13);
   _mm512_storeu_pd(tmp[7],a14);_mm512_storeu_pd(tmp[7]+8,a15);
   for(int r=0;r<8 && qi+r<nq;r++) {
    for(int j=0;j<9;j++)out[(int64_t)(qi+r)*45+pairs[cls*9+j]]+=tmp[r][j];
   }
  }
 }
 return 0;
}
