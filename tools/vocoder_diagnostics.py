"""Diagnose three synthesis-layer suspects on a sustained 'ah' at G4 (392 Hz):
A) naive-saw aliasing, B) 100 Hz envelope-join modulation, C) filter-bank gaps.
Then render v4 with: additive bandlimited saw, 3 ms envelope smoothing,
uniform Q=3.8 (bands cross near -3 dB), no tanh stage."""
import numpy as np
from scipy.signal import butter, sosfilt, welch

SR = 44100
NB = 14
BANDS = [220 * (5600/220) ** (b/(NB-1)) for b in range(NB)]

def naive_saw(f0, n):
    ph = np.cumsum(np.full(n, 2*np.pi*f0/SR))
    return 2*((ph/(2*np.pi)) % 1) - 1

def bl_saw(f0, n):
    t = np.arange(n)/SR
    K = int((SR/2 - 200)//f0)
    out = np.zeros(n)
    for k in range(1, K+1):
        out += np.sin(2*np.pi*k*f0*t)/k
    return out * (2/np.pi)

def inharmonic_hf_db(x, f0):
    f, P = welch(x, SR, nperseg=8192)
    P_db = 10*np.log10(P+1e-18)
    hf = (f > 5000) & (f < 12000)
    harm = np.zeros_like(f, bool)
    k = 1
    while k*f0 < 12000:
        harm |= np.abs(f - k*f0) < 40
        k += 1
    inh = hf & ~harm
    return P_db[inh].max() - P_db[(np.abs(f-f0) < 30)].max()

n = SR*2
print("A) aliasing — loudest inharmonic HF component rel. fundamental:")
print(f"   naive saw     : {inharmonic_hf_db(naive_saw(392, n), 392):6.1f} dB")
print(f"   bandlimited   : {inharmonic_hf_db(bl_saw(392, n), 392):6.1f} dB")

print("B) envelope-join modulation — 100 Hz component of a linearly-")
print("   interpolated 10 ms frame envelope vs after 3 ms smoothing:")
frames = 0.8 + 0.2*np.random.default_rng(3).random(200)   # jittery sustain frames
fi = np.minimum(np.arange(SR*2)/(0.01*SR), 199)
i0 = fi.astype(int); frac = fi-i0; i1 = np.minimum(i0+1, 199)
env = frames[i0]*(1-frac) + frames[i1]*frac
f, P = welch(env - env.mean(), SR, nperseg=1<<15)
p100 = 10*np.log10(P[(np.abs(f-100) < 5)].max()+1e-18)
a = np.exp(-1/(0.003*SR))
env_s = np.zeros_like(env); s = env[0]
for i in range(len(env)):
    s = a*s + (1-a)*env[i]; env_s[i] = s
f, P = welch(env_s - env_s.mean(), SR, nperseg=1<<15)
p100s = 10*np.log10(P[(np.abs(f-100) < 5)].max()+1e-18)
print(f"   linear joins  : {p100:6.1f} dB   after 3 ms smoothing: {p100s:6.1f} dB  (delta {p100s-p100:+.1f})")

print("C) filter-bank flatness — summed |H| ripple across 1-6 kHz:")
def bank_ripple(qlo, qhi):
    imp = np.zeros(SR); imp[0] = 1
    total = np.zeros(SR)
    for b in range(NB):
        q = qhi if BANDS[b] > 2500 else qlo
        bw = BANDS[b]/q
        sos = butter(2, [max(20, BANDS[b]-bw/2), min(SR/2-100, BANDS[b]+bw/2)], "band", fs=SR, output="sos")
        total += sosfilt(sos, imp)
    F = np.fft.rfft(total, SR)
    fr = np.fft.rfftfreq(SR, 1/SR)
    m = (fr > 1000) & (fr < 6000)
    mag = 20*np.log10(np.abs(F[m])+1e-12)
    return mag.max() - mag.min()
print(f"   Q=4/5 split   : {bank_ripple(4,5):6.1f} dB ripple")
print(f"   Q=3.8 uniform : {bank_ripple(3.8,3.8):6.1f} dB ripple")
