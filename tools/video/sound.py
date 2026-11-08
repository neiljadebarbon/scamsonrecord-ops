"""Original sound bed + effects (all synthesized, no licensed audio), then the final mix.
Usage:
  python3 sound.py bed <events.json> <bed.wav>
  python3 sound.py mix <voice.mp3> <bed.wav> <video_noaudio.mp4> <out.mp4>
events.json: {"total": seconds, "events": [[kind, time, gain], ...]} with kind in whoosh, boom, tick, pop, type."""
import json, subprocess, sys, wave
import numpy as np

SR = 48000


def lowpass(x, k):
    c = np.cumsum(np.insert(x, 0, 0.0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([y, np.zeros(len(x) - len(y))])


def make_bed(events_file, out):
    E = json.load(open(events_file))
    T = E['total'] + 0.3
    n = int(T * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(7)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t)
    drone = (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * 55.4 * t) + 0.45 * np.sin(2 * np.pi * 82.41 * t)
             + 0.2 * np.sin(2 * np.pi * 110.3 * t)) * lfo
    pulse = np.sin(2 * np.pi * 41.2 * t) * (np.maximum(0, np.sin(2 * np.pi * 1.0 * t)) ** 8)
    brown = np.cumsum(rng.normal(0, 1, n)); brown -= lowpass(brown, 4800); brown /= np.max(np.abs(brown)) + 1e-9
    L = 0.06 * drone + 0.05 * pulse + 0.022 * brown
    L *= np.minimum(1, t / 1.2) * np.minimum(1, (T - t) / 1.2)
    R = L.copy()

    def add(sig, at, gain, pan=0.0):
        i = int(at * SR); j = min(n, i + len(sig))
        if 0 <= i < n:
            L[i:j] += gain * (1 - max(0, pan)) * sig[:j - i]
            R[i:j] += gain * (1 + min(0, pan)) * sig[:j - i]

    def boom(d=1.4):
        tt = np.arange(int(d * SR)) / SR
        f = 42 + 90 * np.exp(-tt * 9)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.0)
        nz = rng.normal(0, 1, len(tt)) * np.exp(-tt * 38)
        return s + 0.3 * lowpass(nz, 6)

    def whoosh(d=0.5):
        m = int(d * SR); tt = np.arange(m) / SR
        env = np.sin(np.pi * tt / d) ** 2
        return lowpass(rng.normal(0, 1, m), 10) * 3.2 * env

    def tick():
        m = int(0.025 * SR); tt = np.arange(m) / SR
        return np.sin(2 * np.pi * 2300 * tt) * np.exp(-tt * 300)

    def pop():
        m = int(0.12 * SR); tt = np.arange(m) / SR
        f = 520 + 900 * np.exp(-tt * 40)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 34)

    def typ():
        m = int(0.03 * SR); tt = np.arange(m) / SR
        return lowpass(rng.normal(0, 1, m), 3) * np.exp(-tt * 220) * 1.4

    gen = {'boom': boom, 'whoosh': whoosh, 'tick': tick, 'pop': pop, 'type': typ}
    for kind, at, gain in E['events']:
        add(gen[kind](), at, gain, pan=float(rng.uniform(-0.25, 0.25)) if kind in ('pop', 'type', 'whoosh') else 0.0)
    st = np.stack([L, R], 1)
    st = st / (np.max(np.abs(st)) + 1e-9) * 0.6
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes())
    print('bed', out, round(T, 2), 's')


def mix(voice, bed, video, out):
    fc = ('[0:a]aresample=48000,aformat=channel_layouts=stereo,apad,asplit=2[v1][v2];'
          '[1:a]volume=0.85[b];[b][v2]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=400[bd];'
          '[v1][bd]amix=inputs=2:duration=shortest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', voice, '-i', bed, '-i', video, '-filter_complex', fc,
                    '-map', '2:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                    '-shortest', '-movflags', '+faststart', out], check=True)
    print('mixed', out)


if __name__ == '__main__':
    if sys.argv[1] == 'bed':
        make_bed(sys.argv[2], sys.argv[3])
    else:
        mix(*sys.argv[2:6])
