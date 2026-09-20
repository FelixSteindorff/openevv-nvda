"""Check spaced punctuation without removing NVDA's prosody or spelling cues.

No installed NVDA configuration is read or changed. With --dll, compare the
driver's output to raw ECI input in fresh processes, avoiding legacy state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import sequence
from settings import simulated, wait


CASES = {
    "parentheses": ("Test ( zum Beispiel so ) weiter.", "Test (zum Beispiel so) weiter."),
    "colon": ("Test : weiter.", "Test: weiter."),
    "both": ("Test ( Text ) : weiter.", "Test (Text): weiter."),
}


def check_driver(e, mod):
    original = e.Engine
    e.Engine = sequence.FakeEngine
    d = mod.SynthDriver()
    try:
        for language in e.LOCALES:
            for source, expected in CASES.values():
                want = expected if e.encodingOf(language) == "cp1252" else source
                assert d._processText(source, language) == want
                assert d._processText(source, language, spelling=True) == source
        d.language = "de_DE"
        for source, expected in CASES.values():
            assert sequence.spoken(d, [source]) == sequence.spoken(d, [expected])
        assert sequence.spoken(d, ["Test ( ", "Text", " )", " : ", "weiter."]) == sequence.spoken(
            d, ["Test (Text): weiter."]
        )
        for source in ("12:30", "https://example.org", "C:\\Users", "3:2", "(Text)",
                       "Text: weiter", "Text\n: weiter", "(\nText\n)",
                       "Klammer auf Text Klammer zu Doppelpunkt", "left paren text right paren colon"):
            assert d._processText(source) == source
        assert d._processText("(  Text  ) : weiter") == "(Text): weiter"
        assert d._processText("(\u00a0Text\u00a0)\u00a0: weiter") == "(Text): weiter"
        assert d._processText("( ( Text ) )") == "((Text))"
        # NVDA supplies spoken symbol names at higher levels. Retained raw
        # marks must not produce duplicate names or remove the spoken names.
        source = "Test ( Klammer auf Text Klammer zu ) : Doppelpunkt weiter."
        assert d._processText(source) == "Test (Klammer auf Text Klammer zu): Doppelpunkt weiter."
        chars = sequence.spoken(d, [sequence.CharacterModeCommand(True), "( Text ) :",
                                   sequence.CharacterModeCommand(False), "Test : weiter."])
        assert ("addText", b"( Text ) :") in chars
        assert ("addText", b"Test: weiter.") in chars
        assert chars.count(("addText", b"`ts1 ")) == 1
        assert chars.count(("addText", b"`ts0 ")) == 1
        # Index, language and prosody commands are never merged or discarded.
        items = ["a", "b", sequence.IndexCommand(3), "c", "d", sequence.LangChangeCommand("en"),
                 sequence.CharacterModeCommand(True), "(", " )"]
        joined = list(mod._joinAdjacentText(items))
        assert joined == ["ab", items[2], "cd", items[5], items[6], "( )"]
        for mark in ("(", ")", ":"):
            # A standalone character has no neighbouring text to attach to.
            # Do not silently drop explicit character requests.
            assert d._processText(mark, spelling=True) == mark
        d.voiceTags = True
        assert d._processText("`ts1 ( Text ) :") == "`ts1 ( Text ) :"
    finally:
        d.terminate()
        e.Engine = original
    print("PASS: punctuation spacing, split text, spelling, spoken symbol names, commands, times and URLs")


def render(dll, locale, case, variant, out):
    e, mod = simulated()
    import nvwave
    from windows import WavePlayer
    nvwave.WavePlayer = WavePlayer
    e.libraryPath = lambda: str(dll.resolve())
    d = mod.SynthDriver()
    try:
        d.language = locale
        wait(d._engine)
        source, reference = CASES[case]
        if variant == "driver":
            d.speak([source])
        else:
            text = reference if variant == "reference" else source
            eng = d._engine
            eng.post([(eng.addText, (e.encodeText(text, d._language),)), (eng.synthesize, (True,))])
        wait(d._engine)
        pcm = b"".join(d._engine.player.chunks)
        assert pcm and any(pcm), (locale, case, variant)
        (out / f"{locale}-{case}-{variant}.pcm").write_bytes(pcm)
        if locale in ("de_DE", "en_US") and variant != "driver":
            reply = []
            d.requestPhonemes(text, d._language, lambda value, error: reply.append((value, error)))
            wait(d._engine)
            assert reply and not reply[0][1], reply
            (out / f"{locale}-{case}-{variant}.json").write_text(json.dumps(reply), encoding="utf-8")
    finally:
        d.terminate()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dll", type=Path)
    p.add_argument("--out", type=Path, default=Path("build/punctuation-test"))
    p.add_argument("--child", nargs=3)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.child:
        render(a.dll, *a.child, a.out)
        return
    e, mod = simulated()
    check_driver(e, mod)
    if not a.dll:
        return
    results = []
    for language, locale in e.LOCALES.items():
        if e.encodingOf(language) != "cp1252":
            continue
        for case in CASES:
            audio = {}
            for variant in ("driver", "reference", "legacy"):
                subprocess.run([sys.executable, __file__, "--dll", str(a.dll), "--out", str(a.out),
                                "--child", locale, case, variant], check=True, capture_output=True, timeout=45)
                audio[variant] = (a.out / f"{locale}-{case}-{variant}.pcm").read_bytes()
            assert audio["driver"] == audio["reference"], (locale, case)
            if locale in ("de_DE", "en_US"):
                assert audio["driver"] != audio["legacy"], (locale, case, "legacy output persists")
            results.append(dict(language=locale, case=case, reference_equal=True,
                                legacy_different=audio["driver"] != audio["legacy"],
                                sha256=hashlib.sha256(audio["driver"]).hexdigest()))
        print("PASS:", locale, "spaced marks match attached punctuation PCM", flush=True)
    (a.out / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
