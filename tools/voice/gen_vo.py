"""Generate an episode voiceover from a script JSON: [[tag, text, pause_after_seconds], ...]
Usage: python3 tools/voice/gen_vo.py <voice.json> <workdir> <out.mp3> [--assemble-only]
Per paragraph: up to 5 takes, keep the first that passes
  - no stutter at the start (repeated word or sound)
  - no doubled word the script doesn't have
  - pace 115 to 235 wpm (catches doubled phrases)
  - no whispering (voiced share of the loud frames at least 0.58)
Then joins paragraphs with the given pauses, slows 5% and normalizes to about -16 LUFS.
Writes <out>.timeline.json with each paragraph's start time in the final file."""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tts import tts
import qc

TEMPO = float(os.environ.get('TEMPO', '0.95'))


def dur(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True).stdout)


def plain(t):
    return re.sub(r'\[[^\]]*\]', '', t).strip()


def build(script, wd, out):
    S = json.load(open(script))
    os.makedirs(wd, exist_ok=True)
    R = []
    for i, (tag, text, pause) in enumerate(S):
        words = len(plain(text).split())
        best, log = None, []
        for n in range(5):
            f = '%s/p%02d_t%d.mp3' % (wd, i, n)
            if not os.path.exists(f):
                tts(tag + text, f)
            d = dur(f)
            wpm = words / d * 60
            st = qc.start_stutter(f)
            rw = qc.repeated_word(f, text)
            wh = qc.whisper(f)
            ok = st is None and rw is None and wh is None and 115 <= wpm <= 235
            score = (st is None) * 4 + (rw is None) * 3 + (wh is None) * 5 + (115 <= wpm <= 235) * 4
            log.append(dict(n=n, dur=round(d, 2), wpm=round(wpm), stutter=st, repeat=rw, whisper=wh))
            if best is None or score > best[0]:
                best = (score, f, ok)
            if ok:
                break
        R.append(dict(i=i, file=best[1], passed=best[2], pause=pause, log=log))
        print(i, os.path.basename(best[1]), 'ok' if best[2] else 'BEST-EFFORT', log[-1], flush=True)
    json.dump(R, open(wd + '/takes.json', 'w'), indent=1)
    assemble(S, R, wd, out)


def assemble(S, R, wd, out):
    parts, tl, t = [], [], 0.0
    for r in R:
        o = r['file'][:-4] + '.trim.wav'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', r['file'], '-af',
                        'silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse,'
                        'silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.12,areverse',
                        '-ac', '1', '-ar', '44100', o], check=True)
        parts.append(o)
        d = dur(o)
        tl.append(dict(i=r['i'], start=round(t / TEMPO, 3), end=round((t + d) / TEMPO, 3), text=plain(S[r['i']][1])))
        t += d + r['pause']
        if r['pause'] > 0:
            z = '%s/z%02d.wav' % (wd, r['i'])
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
                            '-t', str(r['pause']), z], check=True)
            parts.append(z)
    lst = wd + '/list.txt'
    open(lst, 'w').write(''.join("file '%s'\n" % os.path.abspath(x) for x in parts))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', wd + '/raw.wav'], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wd + '/raw.wav', '-af',
                    'atempo=%s,loudnorm=I=-16:TP=-1.5:LRA=11' % TEMPO, '-ar', '44100', '-ac', '1', '-b:a', '192k', out], check=True)
    d = dur(out)
    w = sum(len(plain(x[1]).split()) for x in S)
    json.dump(tl, open(out[:-4] + '.timeline.json', 'w'), indent=1)
    print('OUT %s %.1fs %d words %d wpm' % (out, d, w, w / d * 60))


if __name__ == '__main__':
    if len(sys.argv) > 4 and sys.argv[4] == '--assemble-only':
        S = json.load(open(sys.argv[1]))
        R = json.load(open(sys.argv[2] + '/takes.json'))
        assemble(S, R, sys.argv[2], sys.argv[3])
    else:
        build(*sys.argv[1:4])
