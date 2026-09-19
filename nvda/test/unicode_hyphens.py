"""Compare Unicode hyphens with ASCII hyphens through the real packaged DLL.

Use a fresh process per rendering so legacy DLL global/arena state cannot
leak across comparisons. The player records PCM without audible playback.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

import sequence
from settings import simulated, wait

LANGUAGES = ('en_US', 'en_GB', 'de_DE', 'es_ES', 'es_MX', 'fr_FR',
             'fr_CA', 'it_IT', 'ja_JP', 'pl_PL')
SENTENCE = 'Mit dem THE-DECODER-Abo liest du werbefrei und wirst Teil unserer Community: Diskutiere im...'
VARIANTS = {'ascii': '-', 'hyphen': '\u2010', 'nonbreaking': '\u2011', 'question': '?'}


def render(addon, out, locale, variant):
    sequence.ADDON = str(addon.resolve())
    e, driver = simulated()
    import nvwave
    from windows import WavePlayer
    nvwave.WavePlayer = WavePlayer
    e.libraryPath = lambda: str((addon / 'synthDrivers/openevv_engine/eci.dll').resolve())
    d = driver.SynthDriver()
    try:
        d.language, d.voice = locale, '1'
        wait(d._engine)
        text = SENTENCE if locale in ('de_DE', 'en_US') else 'THE-DECODER-Abo.'
        d.speak([text.replace('-', VARIANTS[variant])])
        wait(d._engine)
        pcm = b''.join(d._engine.player.chunks)
        assert pcm and any(pcm), (locale, variant)
        with wave.open(str(out / f'{locale}-{variant}.wav'), 'wb') as w:
            w.setparams((1, 2, 11025, 0, 'NONE', 'not compressed'))
            w.writeframes(pcm)
    finally:
        d.terminate()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--addon', type=Path, required=True)
    p.add_argument('--out', type=Path, default=Path('build/hyphen-fix-test/hyphens'))
    p.add_argument('--child', nargs=2)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.child:
        render(a.addon, a.out, *a.child)
        return
    results = []
    for locale in LANGUAGES:
        audio = {}
        for variant in VARIANTS:
            r = subprocess.run([sys.executable, __file__, '--addon', str(a.addon),
                                '--out', str(a.out), '--child', locale, variant],
                               capture_output=True, timeout=45)
            assert r.returncode == 0, (locale, variant, r.stdout, r.stderr)
            with wave.open(str(a.out / f'{locale}-{variant}.wav'), 'rb') as w:
                audio[variant] = w.readframes(w.getnframes())
        assert audio['ascii'] == audio['hyphen'] == audio['nonbreaking'], locale
        if locale in ('de_DE', 'en_US'):
            assert audio['ascii'] != audio['question'], locale
        results.append(dict(language=locale, matches_ascii_hyphen=True,
                            differs_from_question=audio['ascii'] != audio['question'],
                            samples=len(audio['ascii'])//2,
                            sha256=hashlib.sha256(audio['ascii']).hexdigest()))
        print('PASS:', locale, 'Unicode hyphens match ASCII PCM', flush=True)
    (a.out / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
