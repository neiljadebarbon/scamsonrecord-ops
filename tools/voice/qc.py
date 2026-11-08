"""Offline checks on a voice take (pocketsphinx): repeated word or repeated opening sounds."""
import os, re, subprocess

_DEC = {}


def _decoders():
    if not _DEC:
        from pocketsphinx import Decoder, get_model_path
        mp = os.path.join(get_model_path(), 'en-us')
        _DEC['p'] = Decoder(hmm=os.path.join(mp, 'en-us'), allphone=os.path.join(mp, 'en-us-phone.lm.bin'),
                            lw=2.0, beam=1e-20, pbeam=1e-20, loglevel='FATAL')
        _DEC['w'] = Decoder(hmm=os.path.join(mp, 'en-us'), lm=os.path.join(mp, 'en-us.lm.bin'),
                            dict=os.path.join(mp, 'cmudict-en-us.dict'), loglevel='FATAL')
    return _DEC


def pcm(f, seconds=None):
    a = ['ffmpeg', '-loglevel', 'error', '-i', f]
    if seconds:
        a += ['-t', str(seconds)]
    return subprocess.run(a + ['-ar', '16000', '-ac', '1', '-f', 's16le', '-'], capture_output=True).stdout


def start_stutter(f):
    """Reason string if the take repeats its first word or opening sounds, else None."""
    a = pcm(f, 2.5)
    D = _decoders()
    w = D['w']; w.start_utt(); w.process_raw(a, full_utt=True); w.end_utt()
    hw = (w.hyp().hypstr if w.hyp() else '').split()
    p = D['p']; p.start_utt(); p.process_raw(a, full_utt=True); p.end_utt()
    ph = [s.word for s in p.seg() if s.word not in ('SIL', '+SPN+', '+NSN+')]
    if len(hw) >= 2 and hw[0] == hw[1]:
        return 'repeat word ' + hw[0]
    for L in (2, 3):
        if len(ph) >= 2 * L + 1 and ph[:L] == ph[L:2 * L]:
            return 'repeat start ' + ' '.join(ph[:L])
    return None


def repeated_word(f, text):
    """Reason string if the take doubles a word the script does not double."""
    a = pcm(f)
    w = _decoders()['w']; w.start_utt(); w.process_raw(a, full_utt=True); w.end_utt()
    hw = (w.hyp().hypstr if w.hyp() else '').split()
    tw = re.findall(r"[a-z']+", re.sub(r'\[[^\]]*\]', '', text).lower())
    doubled_in_script = {tw[i] for i in range(1, len(tw)) if tw[i] == tw[i - 1]}
    for i in range(1, len(hw)):
        if hw[i] == hw[i - 1] and hw[i] not in doubled_in_script and len(hw[i]) > 2:
            return 'repeat word ' + hw[i]
    return None
