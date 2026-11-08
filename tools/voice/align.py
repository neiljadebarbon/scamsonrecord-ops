"""Word timings for a voiceover with a known script (pocketsphinx forced alignment).
Usage: python3 tools/voice/align.py <voice.mp3> <voice.timeline.json> <out_words.json>
Writes [{paragraph, words: [[word, start, end], ...]}] with times in seconds from the start of the file."""
import json, os, re, subprocess, sys
from pocketsphinx import Decoder, get_model_path

MP = os.path.join(get_model_path(), 'en-us')


def norm_words(text):
    t = re.sub(r'\[[^\]]*\]', '', text).replace('-', ' ')
    return re.findall(r"[A-Za-z']+", t)


def align(mp3, start, end, text):
    a = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(start), '-to', str(end), '-i', mp3,
                        '-ar', '16000', '-ac', '1', '-f', 's16le', '-'], capture_output=True).stdout
    d = Decoder(hmm=os.path.join(MP, 'en-us'), dict=os.path.join(MP, 'cmudict-en-us.dict'), loglevel='FATAL')
    disp = norm_words(text)
    low = [w.lower() for w in disp]
    d.set_align_text(' '.join(low))
    d.start_utt(); d.process_raw(a, full_utt=True); d.end_utt()
    al = [(x.word, x.start_frame / 100, (x.end_frame + 1) / 100) for x in d.seg() if x.word not in ('<s>', '</s>', '<sil>', '[NOISE]')]
    out, j = [], 0
    for name, t0, t1 in al:
        n = re.sub(r'\(\d+\)', '', name)
        while j < len(low) and low[j] != n:
            j += 1
        if j < len(low):
            out.append([disp[j], round(start + t0, 3), round(start + t1, 3)])
            j += 1
    return out


if __name__ == '__main__':
    mp3, tlf, outf = sys.argv[1:4]
    tl = json.load(open(tlf))
    res = []
    for k, p in enumerate(tl):
        s = max(0.0, p['start'] - 0.05)
        e = p['end'] + 0.15
        words = align(mp3, s, e, p['text'])
        res.append({'paragraph': k, 'start': p['start'], 'end': p['end'], 'expected': len(norm_words(p['text'])), 'words': words})
        print(k, '%d/%d words aligned' % (len(words), len(norm_words(p['text']))))
    json.dump(res, open(outf, 'w'), indent=1)
