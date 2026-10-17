/* Exact uint8 dot products with AVX512-VNNI, 8 queries x 16 SV microtile.
 * No images/labels/answers are embedded; model data is runtime input.
 * Original D=784 is a multiple of four. Bound D*255^2=50,979,600 < INT32_MAX.
 */
#include <stdint.h>
#include <string.h>
#include <immintrin.h>
#include <omp.h>

int has_vnni(void) {
#if defined(__x86_64__)
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx512vnni") && __builtin_cpu_supports("avx512bw");
#else
    return 0;
#endif
}

#define STEP(A,XP) do { uint32_t v; memcpy(&v,(XP)+4*k,4); \
    A = _mm512_dpbusd_epi32(A, _mm512_set1_epi32((int)v), b); } while(0)

int u8_dot(const uint8_t *x, const int8_t *packed, int32_t *out,
           int nq, int ns, int d) {
    if(d!=784 || nq<1 || ns<1) return 1;
    const int kd=d/4, nb=(ns+15)/16;
    #pragma omp parallel for schedule(static) num_threads(2)
    for(int qi=0;qi<nq;qi+=8) {
        const uint8_t *xp[8]; int32_t offset[8];
        for(int r=0;r<8;r++) {
            xp[r]=x+(qi+r<nq ? qi+r:qi)*d;
            int32_t sum=0;for(int z=0;z<d;z++)sum+=xp[r][z];
            offset[r]=128*sum;
        }
        for(int sj=0;sj<nb;sj++) {
            __m512i a0=_mm512_setzero_si512(), a1=a0,a2=a0,a3=a0,a4=a0,a5=a0,a6=a0,a7=a0;
            const int8_t *bp=packed+(int64_t)sj*kd*64;
            for(int k=0;k<kd;k++) {
                __m512i b=_mm512_loadu_si512((const void*)(bp+k*64));
                STEP(a0,xp[0]);STEP(a1,xp[1]);STEP(a2,xp[2]);STEP(a3,xp[3]);
                STEP(a4,xp[4]);STEP(a5,xp[5]);STEP(a6,xp[6]);STEP(a7,xp[7]);
            }
            __m512i acc[8]={a0,a1,a2,a3,a4,a5,a6,a7};
            int count=ns-sj*16;if(count>16)count=16;
            __mmask16 mask=(__mmask16)((1u<<count)-1u);
            for(int r=0;r<8 && qi+r<nq;r++) {
                __m512i v=_mm512_add_epi32(acc[r],_mm512_set1_epi32(offset[r]));
                _mm512_mask_storeu_epi32(out+(int64_t)(qi+r)*ns+sj*16,mask,v);
            }
        }
    }
    return 0;
}
