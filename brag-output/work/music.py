# Original 23 s soundtrack for the Trackback brag video: 120 BPM, A minor intro lifting to C major at 6.0 s.
# Music and effects are written together, in key, and mixed with effects under the music.
import numpy as np, wave

SR = 44100
DUR = 23.0
N = int(SR * DUR)
t_all = np.arange(N) / SR
BEAT = 0.5

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def env(n, a, d, s_lvl, r, hold):
    a, d, r, hold = int(a * SR), int(d * SR), int(r * SR), int(hold * SR)
    e = np.zeros(n)
    seg = np.concatenate([np.linspace(0, 1, max(a, 1)), np.linspace(1, s_lvl, max(d, 1)), np.full(max(hold - a - d, 0), s_lvl), np.linspace(s_lvl, 0, max(r, 1))])
    m = min(n, len(seg)); e[:m] = seg[:m]; return e
def onepole(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR); y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc; y[i] = acc
    return y
def lp(x, cutoff):  # vectorised-enough one-pole via scipy-free recursion on chunks
    return onepole(x, cutoff)
def add(buf, start, sig, gain=1.0):
    sig = sig.copy(); k = min(len(sig) // 2, int(0.006 * SR))
    sig[-k:] *= np.linspace(1, 0, k); sig[:k] *= np.linspace(0, 1, k) if sig is not None and start > 0.05 and False else 1
    i = int(start * SR); j = min(len(buf), i + len(sig))
    if i < len(buf): buf[i:j] += sig[: j - i] * gain

music = np.zeros(N); sfx = np.zeros(N); pads = np.zeros(N); drums = np.zeros(N)

# chords per 2 s bar (MIDI roots and voicings)
A, F, G, C = [57, 60, 64], [53, 57, 60], [55, 59, 62], [48, 52, 55, 60]
bars = [A, F, G, C, G, A, F, C, G, F, C, C]
roots = [45, 41, 43, 36, 43, 45, 41, 36, 43, 41, 36, 36]

# pad: detuned saws through a soft low-pass, swells in over the intro
for b, ch in enumerate(bars):
    start = b * 2.0; n = int(2.25 * SR); tt = np.arange(n) / SR
    sig = np.zeros(n)
    for m in ch:
        for det in (-0.08, 0.0, 0.07):
            f = hz(m + 12) * 2 ** (det / 12)
            sig += 2 * ((tt * f) % 1.0) - 1
    sig /= len(ch) * 3
    e = env(n, 0.25, 0.3, 0.8, 0.35, 2.0)
    add(pads, start, sig * e, 0.30 if b < 3 else 0.12)
pads = lp(pads, 1400)

# pluck arpeggio (8ths): decaying triangle, brighter after the lift
for b, ch in enumerate(bars):
    if b * 2.0 >= 22.0: break
    seq = (ch + [ch[0] + 12, ch[1] + 12])[:4]
    seq = seq + seq[::-1]
    for k, m in enumerate(seq):
        st = b * 2.0 + k * 0.25; n = int(0.4 * SR); tt = np.arange(n) / SR
        f = hz(m + 12)
        tri = 2 * np.abs(2 * ((tt * f) % 1.0) - 1) - 1
        sig = (tri * 0.7 + np.sin(2 * np.pi * f * 2 * tt) * 0.3) * np.exp(-tt * 9)
        add(music, st, sig, 0.22 if b < 3 else 0.13)

# bass from 3.0 s: root on 8ths with a pumping envelope
for b in range(len(bars)):
    if b * 2.0 < 3.0 and b != 1: continue
    for k in range(8):
        st = b * 2.0 + k * 0.25
        if st < 3.0 or st >= 22.0: continue
        n = int(0.24 * SR); tt = np.arange(n) / SR; f = hz(roots[b])
        sig = np.tanh(1.8 * np.sin(2 * np.pi * f * tt)) * np.minimum(1, tt * 60) * np.exp(-tt * 5)
        add(music, st, sig, 0.30)

# drums
def kick(g=1.0):
    n = int(0.35 * SR); tt = np.arange(n) / SR
    f = 45 + 110 * np.exp(-tt * 28); ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-tt * 9) * g
def hat():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    x = np.random.default_rng(7).standard_normal(n); x = lp(x - lp(x, 6000), 9500)
    return x * np.exp(-tt * 60)
def clap():
    n = int(0.22 * SR); tt = np.arange(n) / SR
    x = np.random.default_rng(3).standard_normal(n); x = lp(x - lp(x, 900), 5000)
    e = np.exp(-tt * 18) + 0.6 * np.exp(-((tt - 0.012) * 300) ** 2) + 0.5 * np.exp(-((tt - 0.024) * 300) ** 2)
    return x * e
K, H, CL = kick(), hat(), clap()
for i in range(int(22.0 / BEAT)):
    st = i * BEAT
    if st >= 3.0: add(drums, st, K, 0.55)
    elif i % 2 == 0 and st >= 1.0: add(drums, st, K, 0.28)
    if st >= 6.0:
        add(drums, st + 0.25, H, 0.06)
        if i % 2 == 1: add(drums, st, CL, 0.22)
add(drums, 22.0, K, 0.5)

# sidechain-ish duck of pads/music on kicks
duck = np.ones(N)
for i in range(int(22.0 / BEAT)):
    st = i * BEAT
    if st >= 3.0:
        a = int(st * SR); n = int(0.25 * SR); tt = np.arange(n) / SR
        duck[a:a + n] = np.minimum(duck[a:a + n], 1 - 0.45 * np.exp(-tt * 14) * np.minimum(1, tt / 0.008))

# ---------------- effects, in key (A / E / C), sat under the music
def thud(g):
    n = int(0.6 * SR); tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * (hz(33) + 60 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 7)
    x = np.random.default_rng(11).standard_normal(n); x = lp(x, 700) * np.exp(-tt * 25)
    return (body + 0.8 * x) * g
def bell(midis, decay=3.0):
    n = int(1.6 * SR); tt = np.arange(n) / SR; s = np.zeros(n)
    for m in midis:
        f = hz(m); s += np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 6)
    return s / len(midis) * np.exp(-tt * decay) * np.minimum(1, tt * 400)
def riser(a, b):
    n = int((b - a) * SR); tt = np.arange(n) / SR
    x = np.random.default_rng(5).standard_normal(n); x = x - lp(x, 1500)
    return x * (tt / tt[-1]) ** 2.2 * 0.6

add(sfx, 0.02, thud(0.5))
add(sfx, 3.72, thud(0.75))
add(sfx, 3.72, bell([45, 52], 4.0), 0.25)
add(sfx, 5.0, riser(5.0, 6.0), 0.18)
add(sfx, 10.1, bell([88], 14), 0.12)          # tick on the sweep (E6)
add(sfx, 12.75, bell([88, 93], 3.5), 0.22)    # the ping (E6 + A6)
add(sfx, 16.15, bell([72, 76, 79], 2.5), 0.16)  # payoff chord (C)
add(sfx, 20.5, thud(0.7))

# small room: two feedback delays on sfx and pluck for shared space
def room(x, taps=((0.083, 0.30), (0.127, 0.22), (0.191, 0.15))):
    y = x.copy()
    for d, g in taps:
        k = int(d * SR); y[k:] += x[:-k] * g
    return lp(y, 5000)

mix = (music * duck + pads * duck + drums + room(sfx) * 0.9)
mix = room(mix, ((0.031, 0.12), (0.057, 0.08)))
# tail: let the last C ring, fade the last 0.9 s
fade = np.ones(N); a = int((DUR - 0.9) * SR); fade[a:] = np.linspace(1, 0, N - a) ** 1.5
mix *= fade
mix = np.tanh(mix * 1.3) / np.tanh(1.3)
mix *= 0.89 / np.max(np.abs(mix))
st = np.stack([mix, np.roll(mix, int(0.011 * SR)) * 0.96 + mix * 0.04], axis=1)
pcm = (st * 32767).astype('<i2')
with wave.open('music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('wrote music.wav', DUR, 's')
