"""ElevenLabs text-to-speech in the channel voice.
Key: env XI or ELEVENLABS_API_KEY, else a local .env file (never committed; this repo is public)."""
import json, os, time, urllib.request, urllib.error

VOICE = os.environ.get('ELEVENLABS_VOICE_ID', '7mN3HOhMedH0rcubaqVy')
MODEL = 'eleven_v4'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def key():
    for name in ('XI', 'ELEVENLABS_API_KEY'):
        if os.environ.get(name):
            return os.environ[name]
    for f in (os.path.join(ROOT, '.env'), os.path.expanduser('~/.secrets/elevenlabs.env')):
        if os.path.exists(f):
            for line in open(f):
                if line.startswith(('XI=', 'ELEVENLABS_API_KEY=')):
                    return line.strip().split('=', 1)[1]
    raise RuntimeError('no ElevenLabs key: set XI or ELEVENLABS_API_KEY')


def tts(text, out, stability=None, similarity=0.8):
    if stability is None:
        stability = float(os.environ.get('STABILITY', '0.4'))
    body = json.dumps({'text': text, 'model_id': MODEL,
                       'voice_settings': {'stability': stability, 'similarity_boost': similarity}}).encode()
    url = 'https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_192' % VOICE
    req = urllib.request.Request(url, data=body, headers={'xi-api-key': key(), 'Content-Type': 'application/json'})
    for k in range(4):
        try:
            open(out, 'wb').write(urllib.request.urlopen(req, timeout=180).read())
            return
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                time.sleep(5 * (k + 1))
                continue
            raise RuntimeError('%s %s' % (e.code, e.read().decode()[:300]))
