"""Ground-truth offline render of the v3 vocoder engine: the full 14-note
Amazing Grace phrase, exactly the widget algorithm, no real-time scheduling.
Outputs two WAVs: full v3, and the same engine with diction=0 (control)."""
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100
NB = 14
BANDS = [220 * (5600/220) ** (b/(NB-1)) for b in range(NB)]
FR = 0.01
VOWELS = [
    dict(f=[300,870,2240],  g=[1,.35,.12]),
    dict(f=[570,840,2410],  g=[1,.45,.15]),
    dict(f=[730,1090,2440], g=[1,.6,.2]),
    dict(f=[530,1840,2480], g=[1,.5,.22]),
    dict(f=[270,2290,3010], g=[1,.3,.28]),
]
Qms = 560
MEL = [  # note, beats, vowelCC, syl, vel, onset, coda
    (55,1,64,"A",72,"",""),
    (60,2,80,"ma",84,"m",""),(64,1,120,"zing",80,"z","n"),
    (64,2,96,"grace",88,"g","s"),(62,1,64,"how",78,"h",""),
    (60,2,127,"sweet",84,"s","t"),(57,1,38,"the",74,"d",""),
    (55,3,58,"sound",78,"s","n"),
    (55,1,58,"that",74,"d","t"),
    (60,2,96,"saved",86,"s","d"),(64,1,32,"a",76,"",""),
    (64,2,96,"wretch",88,"r","ch"),(62,1,70,"like",80,"l","k"),
    (67,3,127,"me",104,"m",""),
]

def mtof(n): return 440*2**((n-69)/12)

def vowel_spectrum(cc):
    pos = max(0, min(4, (cc/127)*4)); i = int(pos); j = min(i+1,4); t = pos-i
    F = [VOWELS[i]["f"][k]*(VOWELS[j]["f"][k]/VOWELS[i]["f"][k])**t for k in range(3)]
    G = [VOWELS[i]["g"][k]+(VOWELS[j]["g"][k]-VOWELS[i]["g"][k])*t for k in range(3)]
    s = np.array([sum(G[k]*np.exp(-0.5*(np.log(BANDS[b]/F[k])/0.20)**2) for k in range(3)) for b in range(NB)])
    return s/s.max()

def tilt_hf(s):
    return s*np.array([min(1.0,(4200/BANDS[b])**0.6) for b in range(NB)])

def band_only(lo,hi,g):
    return np.array([g if lo <= BANDS[b] <= hi else 0.0 for b in range(NB)])

SIL = np.full(NB, 0.004)
UNVOICED_ONSETS = set("s z f h t k ch".split())

def cons_frames(code, vw, dic):
    seg=[]
    def push(spec,voi,ms,amp): seg.append((spec*amp, voi, max(1,round(ms/10))))
    vsp = vowel_spectrum(vw)
    if code=="s": push(tilt_hf(band_only(3800,5600,1)),0,60,0.28*dic)
    elif code=="z": push(tilt_hf(band_only(3000,5600,1)),0.65,55,0.18*dic)
    elif code=="f": push(tilt_hf(band_only(1800,5000,0.7)),0,55,0.16*dic)
    elif code=="t": push(SIL,1,30,1); push(tilt_hf(band_only(2600,5200,1)),0,20,0.30*dic)
    elif code=="k": push(SIL,1,30,1); push(band_only(1200,2400,1),0,20,0.30*dic)
    elif code=="ch": push(SIL,1,22,1); push(tilt_hf(band_only(1800,4000,1)),0,50,0.26*dic)
    elif code=="b": push(SIL,1,20,1); push(band_only(200,600,1),1,20,0.5*dic)
    elif code=="d": push(SIL,1,20,1); push(band_only(1400,3000,1),1,18,0.28*dic)
    elif code=="g": push(SIL,1,22,1); push(band_only(900,2000,1),1,20,0.30*dic)
    elif code=="h": push(vsp,0,55,0.30*dic)
    elif code in ("m","n"): push(band_only(0,420,1),1,90,0.8)
    elif code=="w": push(vowel_spectrum(0),1,90,0.9)
    elif code in ("l","r"): push(vowel_spectrum(38),1,90,0.9)
    return seg

def build_note(vw,on,co,dur_s,dic,smear_ms):
    N = max(6, round(dur_s/FR))
    bands = np.zeros((NB,N)); voi = np.zeros(N); amp = np.zeros(N)
    f = 0
    def write(seg):
        nonlocal f
        for spec,v,n in seg:
            for _ in range(n):
                if f>=N: return
                bands[:,f]=spec; voi[f]=v; amp[f]=1; f+=1
    if on: write(cons_frames(on,vw,dic))
    vsp = vowel_spectrum(vw)
    if on in UNVOICED_ONSETS and f<N:
        bands[:,f]=vsp*0.15; voi[f]=1; amp[f]=1; f+=1
    glide_from = f if on in ("w","l","r","m","n") else -1
    co_seg = cons_frames(co,vw,dic) if co else []
    co_n = sum(n for _,_,n in co_seg)
    sus_end = N-co_n-3; sus_start=f
    while f<sus_end and f<N:
        t=(f-sus_start)/max(1,sus_end-sus_start)
        blend=min(1,(f-sus_start)/8) if glide_from>=0 else 1
        prev = bands[:,max(0,sus_start-1)] if glide_from>=0 else vsp
        bands[:,f]=prev*(1-blend)+vsp*blend
        voi[f]=1; amp[f]=1-0.1*t; f+=1
    if co: write(co_seg)
    while f<N:
        bands[:,f]=0; voi[f]=voi[max(0,f-1)]; amp[f]=0; f+=1
    a_att=np.exp(-10/max(2,smear_ms)); a_rel=np.exp(-10/4)
    st=np.zeros(NB)
    for i in range(N):
        tgt=bands[:,i]*amp[i]
        for b in range(NB):
            a = a_att if (tgt[b]>=st[b] or BANDS[b]<=2500) else a_rel
            st[b]=a*st[b]+(1-a)*tgt[b]
        bands[:,i]=st.copy()
    sv=0; voi_s=np.zeros(N); a_vup=np.exp(-10/5)
    for i in range(N):
        a = a_vup if voi[i]>=sv else a_att
        sv=a*sv+(1-a)*voi[i]; voi_s[i]=sv
    bands[:,-3]*=0.4; bands[:,-2]=0; bands[:,-1]=0
    return bands, voi_s, N


def render_v4(dic, smear_ms=14, fname="out.wav"):
    """Ground-truth reference render: bandlimited additive saw, Q=4.5 bank,
    alternating band polarity. This file is the SPEC for the vocoder mode."""
    total_ms = sum(round(b*Qms) for _,b,_,_,_,_,_ in MEL) + 600
    NF = round(total_ms/10)
    g_bands = np.zeros((NB,NF)); g_voi = np.ones(NF); g_f0 = np.full(NF, 220.0)
    t = 0
    for note,beats,vw,syl,vel,on,co in MEL:
        dur_s = (round(beats*Qms)-40)/1000
        bands, voi, N = build_note(vw,on,co,dur_s,dic,smear_ms)
        lvl = 0.25+0.5*(vel/127)
        off = round(t/10); n = min(N, NF-off)
        g_bands[:,off:off+n] = bands[:,:n]*lvl
        g_voi[off:off+n] = voi[:n]
        g_f0[off:off+round(round(beats*Qms)/10)] = mtof(note)
        t += round(beats*Qms)
    n_samp = round(NF*0.01*SR)
    tt = np.arange(n_samp)/SR
    fi = np.minimum(np.arange(n_samp)/(0.01*SR), NF-1)
    i0=fi.astype(int); frac=fi-i0; i1=np.minimum(i0+1,NF-1)
    interp = lambda row: row[i0]*(1-frac)+row[i1]*frac
    f0_t = interp(g_f0) + 5*np.sin(2*np.pi*4.8*tt)
    phase = np.cumsum(2*np.pi*f0_t/SR)
    K = int((SR/2-200)//(g_f0.max()+6))
    saw = np.zeros(n_samp)
    for k in range(1, K+1):
        saw += np.sin(k*phase)/k
    saw *= 2/np.pi
    noise = np.random.default_rng(11).standard_normal(n_samp)*0.35
    v = interp(g_voi)
    exc = saw*v + noise*(1-v)*0.4
    out = np.zeros(n_samp)
    for b in range(NB):
        bw = BANDS[b]/4.5
        sos = butter(2,[max(20,BANDS[b]-bw/2),min(SR/2-100,BANDS[b]+bw/2)],"band",fs=SR,output="sos")
        y = sosfilt(sos, exc)*interp(g_bands[b])
        out += -y if b % 2 else y
    out = out/np.max(np.abs(out))*0.89
    fade = round(0.01*SR)
    out[:fade]*=np.linspace(0,1,fade); out[-fade:]*=np.linspace(1,0,fade)
    wavfile.write(fname, SR, (out*32767).astype(np.int16))

if __name__ == "__main__":
    render_v4(1.0, 14, "vocoder_reference_full.wav")
    render_v4(0.0, 14, "vocoder_reference_vowels_only.wav")
    print("reference renders written")
