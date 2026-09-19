"""Unicode boundary audit plus isolated PCM comparisons using the real DLL."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unicodedata
import wave

import sequence
from settings import simulated, wait
from unicode_hyphens import LANGUAGES

LAYOUT = [
    ('soft-hyphen', 'Com\u00admunity', 'Community'),
    ('word-joiner', 'Com\u2060munity', 'Community'),
    ('bom', '\ufeffCommunity', 'Community'),
    ('zero-width-space', 'Hello\u200bworld', 'Hello world'),
    ('bidi', '\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069Hello', 'Hello'),
    ('presentation', 'Hello\ufe0e\ufe0f', 'Hello'),
    ('line-separator', 'Hello\u2028world', 'Hello\nworld'),
    ('paragraph-separator', 'Hello\u2029world', 'Hello\n\nworld'),
    ('hyphens', 'THE\u2010DECODER\u2011Abo', 'THE-DECODER-Abo'),
]
WESTERN = [
    ('thin-space', '12\u2009km', '12 km'),
    ('narrow-space', '12\u202fkm', '12 km'),
    ('figure-space', '12\u2007km', '12 km'),
    ('figure-dash', '12\u201234', '12\u201334'),
    ('horizontal-bar', 'Hello\u2015world', 'Hello\u2014world'),
    ('rare-quotes', '\u201bHello\u201f', '\'Hello"'),
    ('dot-leaders', 'Hello\u2024 world\u2025', 'Hello. world..'),
    ('ligatures', '\ufb00 \ufb01 \ufb02 \ufb03 \ufb04 \ufb05 \ufb06', 'ff fi fl ffi ffl st st'),
    ('capital-sharp-s', 'GRO\u1e9e', 'GROSS'),
    ('width', '\uff21\uff22\uff23\uff11\uff12\uff13\uff0c\uff01', 'ABC123,!'),
]
PRESERVED = '\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df \u2018\u2019\u201a\u201c\u201d\u201e \u2013\u2014 \u2026\u20ac\u00a3\u00a9\u00ae\u2122 \u00b2\u00b3\u00bc\u00bd\u00be ?'
# These are meaningful, not typographic equivalents of ASCII. Keep the
# existing encoding outcome and document the remaining legacy limitation.
UNHANDLED = '\u2212\u2032\u2033\u2192\u2264\U0001f600\u010d\u0142\u03b1\u0416\u200c\u200d\uff40'


def modules(addon):
    sequence.ADDON = str(addon.resolve())
    return simulated()


def check_encoding(e, out):
    count = 0
    for language, locale in e.LOCALES.items():
        codec = e.encodingOf(language)
        for name, text, reference in LAYOUT:
            assert e.encodeText(text, language) == reference.encode(codec), (locale, name)
            count += 1
        if codec == 'cp1252':
            for name, text, reference in WESTERN:
                assert e.encodeText(text, language) == reference.encode(codec), (locale, name)
                count += 1
        else:
            # Never transliterate characters already native to the language.
            for _, text, _ in WESTERN:
                for ch in text:
                    try:
                        native = ch.encode(codec)
                    except UnicodeEncodeError:
                        continue
                    assert e.encodeText(ch, language) == native, (locale, repr(ch))
        assert e.encodeText(PRESERVED, language) == PRESERVED.encode(codec, 'replace'), locale
        assert e.encodeText(UNHANDLED, language) == UNHANDLED.encode(codec, 'replace'), locale
        assert e.encodeText('Cafe\u0301', language) == 'Caf\u00e9'.encode(codec, 'replace')
        assert e.encodeText('`v1', language) == b'`v1'  # Explicit ECI tags still work.
        assert b'`' not in e.encodeText('\uff40v1', language)
    # Inspect all width variants; a new ASCII annotation starter is forbidden.
    for n in range(0xff01, 0xff5f):
        encoded = e.encodeText(chr(n), 0x40000)
        assert b'`' not in encoded
        if n != 0xff40:
            assert encoded == chr(n-0xfee0).encode('ascii')
    before = Path('build/unicode-fix-test/audit-before.json')
    if before.exists():
        rows = json.loads(before.read_text(encoding='utf-8'))
        for row in rows:
            ch = chr(int(row['codepoint'][2:], 16))
            row['after'] = {e.LOCALES[l]: e.encodeText(ch, l).hex()
                            for l in (0x40000, 0x10000, 0x80000, 0x110000)}
        (out / 'audit.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(f'PASS: {count} layout/typography fixtures, native text preservation and no new ECI tags')


def check_sequences(e, driver):
    original = e.Engine
    e.Engine = sequence.FakeEngine
    try:
        d = driver.SynthDriver()
        for group in ('layout', 'typography'):
            assert sequence.spoken(d, [case_text(group, 'input')]) == sequence.spoken(d, [case_text(group, 'reference')]), group
        # Formatting controls cannot hide an ECI tag from the ordinary-text filter.
        assert all(b'`' not in call[1] for call in sequence.spoken(d, ['\ufeff`v1Hello']) if call[0] == 'addText')
        d.terminate()
    finally:
        e.Engine = original
    print('PASS: normalized sentence boundaries and annotation filtering')


def case_text(group, variant):
    cases = LAYOUT if group == 'layout' else WESTERN
    return '. '.join(row[1 if variant == 'input' else 2] for row in cases) + '.'


def render(addon, out, locale, group, variant):
    e, driver = modules(addon)
    import nvwave
    from windows import WavePlayer
    nvwave.WavePlayer = WavePlayer
    e.libraryPath = lambda: str((addon / 'synthDrivers/openevv_engine/eci.dll').resolve())
    d = driver.SynthDriver()
    try:
        d.language, d.voice = locale, '1'
        wait(d._engine)
        d.speak([case_text(group, variant)])
        wait(d._engine)
        pcm = b''.join(d._engine.player.chunks)
        assert pcm and any(pcm), (locale, group, variant)
        with wave.open(str(out / f'{locale}-{group}-{variant}.wav'), 'wb') as w:
            w.setparams((1, 2, 11025, 0, 'NONE', 'not compressed'))
            w.writeframes(pcm)
    finally:
        d.terminate()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--addon', type=Path, required=True)
    p.add_argument('--out', type=Path, default=Path('build/unicode-fix-test/unicode'))
    p.add_argument('--child', nargs=3)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.child:
        render(a.addon, a.out, *a.child)
        return
    e, driver = modules(a.addon)
    check_encoding(e, a.out)
    check_sequences(e, driver)
    results = []
    for locale in LANGUAGES:
        for group in ('layout', 'typography') if locale not in ('ja_JP', 'pl_PL') else ('layout',):
            audio = []
            for variant in ('input', 'reference'):
                r = subprocess.run([sys.executable, __file__, '--addon', str(a.addon),
                                    '--out', str(a.out), '--child', locale, group, variant],
                                   capture_output=True, timeout=45)
                assert r.returncode == 0, (locale, group, variant, r.stdout, r.stderr)
                with wave.open(str(a.out / f'{locale}-{group}-{variant}.wav'), 'rb') as w:
                    audio.append(w.readframes(w.getnframes()))
            assert audio[0] == audio[1], (locale, group)
            results.append(dict(language=locale, group=group, pcm_equal=True,
                                samples=len(audio[0])//2, sha256=hashlib.sha256(audio[0]).hexdigest()))
            print('PASS:', locale, group, 'matches reference PCM', flush=True)
    (a.out / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
