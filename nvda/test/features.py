"""Editor/overlay/preset/WPM/pronunciation checks against the packaged DLL."""
import argparse
import ctypes
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import zipfile

import sequence
from settings import simulated, wait


def archive(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, value in files.items():
            z.writestr("repo/"+name, value)
    return buf.getvalue()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--addon", default="nvda/addon", type=Path)
    p.add_argument("--dll", default="build/multilingual-test/packaged/synthDrivers/openevv_engine/eci.dll", type=Path)
    p.add_argument("--out", default="build/features-test", type=Path)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sequence.ADDON = str(args.addon.resolve())
    e, mod = simulated()
    import config
    import nvwave
    from windows import WavePlayer
    from synthDrivers import _openevv_tools as tools, _openevv_dictionaries as data
    nvwave.WavePlayer = WavePlayer
    e.libraryPath = lambda: str(args.dll.resolve())
    sys.modules["globalVars"] = types.SimpleNamespace(appArgs=types.SimpleNamespace(secure=False))
    import globalVars
    results = {}
    with tempfile.TemporaryDirectory(prefix="openevv-features-") as temporary:
        base = Path(temporary) / "Wörterbücher"
        data.root = lambda: base
        for profile in ("community", "alternative"):
            data.install(profile, archive({"DEUmain.dic": b"nvda\tGuten Morgen\noriginal\tComputer\n",
                                          "ENUmain.dic": b"nvda\tgood morning\n"}))
        rows, revision = data.readCustom(0x40000, 0)
        assert rows == []
        revision = data.saveCustom(0x40000, 0, [("nvda", "Hallo Welt"), ("grüße", "äöüÄÖÜß")], revision)
        assert data.readCustom(0x40000, 0)[0][-1] == ("grüße", "äöüÄÖÜß")
        # External edits and invalid input may not overwrite the user's file.
        saved = data.customFile(0x40000, 0).read_bytes()
        for bad_rows, bad_revision in (([("x", "bad\nentry")], revision), ([("x", "ok")], "stale"),
                                       ([("x", "1"), ("x", "2")], revision)):
            try:
                data.saveCustom(0x40000, 0, bad_rows, bad_revision)
                raise AssertionError("invalid edit accepted")
            except ValueError:
                pass
            assert data.customFile(0x40000, 0).read_bytes() == saved
        for profile in ("community_custom", "alternative_custom"):
            volumes = data.prepared(profile, [0x40000,0x10000])
            merged = dict(data.parse(volumes[0x40000][0][1].read_bytes()))
            assert merged[b"nvda"] == b"Hallo Welt" and merged[b"original"] == b"Computer"
        data.install("community", archive({"DEUmain.dic": b"nvda\tUPDATED\noriginal\tUPDATED\n"}))
        merged = dict(data.parse(data.prepared("community_custom", [0x40000])[0x40000][0][1].read_bytes()))
        assert merged[b"nvda"] == b"Hallo Welt" and merged[b"original"] == b"UPDATED"
        assert data.customFile(0x40000,0).read_bytes() == saved
        results["editor_unicode_atomicity_overlay_update"] = True
        # A saved phonetic entry must produce the same PCM as the explicit
        # phonetic preview on an otherwise identical fresh engine history.
        body = ".2hE.1lo"
        _, english_revision = data.readCustom(0x10000,0)
        data.saveCustom(0x10000,0,[("openevvprobe",tools.annotation(body,"phonemes",0x10000))],english_revision)
        rendered = []
        for dictionary in (True,False):
            voice = mod.SynthDriver()
            try:
                if dictionary:
                    voice.dictionaryProfile = "custom"
                    wait(voice._engine)
                    voice.speak(["openevvprobe"])
                else:
                    voice.previewTool(body,"phonemes",0x10000)
                wait(voice._engine)
                rendered.append(b"".join(voice._engine.player.chunks))
            finally:
                voice.terminate()
        assert rendered[0] and rendered[0] == rendered[1]
        results["phonetic_dictionary_matches_preview"] = True
        d = mod.SynthDriver()
        try:
            d.language, d.voice, d.dictionaryProfile = "de_DE", "4", "community_custom"
            wait(d._engine)
            eng = d._engine
            dll = eng._dll
            dll.eciDictLookup.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_char_p]
            dll.eciDictLookup.restype = ctypes.c_char_p
            lookups = []
            def lookup():
                lookups.append(dll.eciDictLookup(eng._instance, eng._dictionaries[0x40000], 0, b"nvda"))
            eng.control([(lookup,())])
            wait(eng)
            assert lookups == [b"Hallo Welt"]
            before = tools.snapshot(d)
            tools.savePreset("Reed – Grüße", d)
            d.language, d.voice, d.rate = "fr_CA", "6", 90
            tools.applyPreset(d, "Reed – Grüße")
            wait(eng)
            assert tools.snapshot(d) == before and eng.language == 0x40000
            config_before = json.loads(json.dumps(config.conf["speech"]["openevv"]))
            tools.applyPreset(d, "Reed – Grüße")
            wait(eng)
            assert config.conf["speech"]["openevv"] == config_before
            # All persisted settings including overlay and boosted rate round-trip.
            for wanted in (149, 180, 250, 350, 500, 800, 1297):
                percent, boost, actual = tools.wpmChoice(d, wanted)
                d.rateBoost, d.rate = boost, percent
                wait(eng)
                assert tools.rawToWpm(eng.voiceParams[e.VOICE_SPEED]) == actual
            d.saveSettings()
            stored = json.loads(json.dumps(config.conf["speech"]["openevv"]))
            d.rate, d.rateBoost = 20, False
            d.loadSettings()
            wait(eng)
            assert tools.snapshot(d) == stored
            # Validate the whole Python WPM curve against ECI's real-world API.
            checked = []
            def curve():
                speed = eng.getVoiceParam(e.VOICE_SPEED)
                try:
                    for raw in range(251):
                        dll.eciSetVoiceParam(eng._instance,0,e.VOICE_SPEED,raw)
                        dll.eciSetParam(eng._instance,e.PARAM_REAL_WORLD,1)
                        checked.append(dll.eciGetVoiceParam(eng._instance,0,e.VOICE_SPEED) == tools.rawToWpm(raw))
                        dll.eciSetParam(eng._instance,e.PARAM_REAL_WORLD,0)
                finally:
                    dll.eciSetParam(eng._instance,e.PARAM_REAL_WORLD,0)
                    eng.setVoiceParam(e.VOICE_SPEED,speed)
            eng.control([(curve,())])
            wait(eng)
            assert len(checked) == 251 and all(checked)
            results["wpm_eci_curve_checks"] = len(checked)
            # Phoneme analysis leaves the current speech instance and settings intact.
            d.rateBoost, d.rate, d.dictionaryProfile = False, 50, "builtin"
            wait(eng)
            state = tools.snapshot(d)
            phonemes, previews = [], []
            words = {0x10000:"hello",0x10001:"hello",0x40000:"Grüße",0x20000:"niño",
                     0x20001:"niño",0x30000:"bonjour",0x30001:"bonjour",0x50000:"buongiorno"}
            formats = {"ordinal":"12", "telephone":"0123 456789", "currency":"12.50",
                       "date_dmy":"19/09/2026", "date_mdy":"09/19/2026", "date_ymd":"2026/09/19"}
            for language, word in words.items():
                reply = []
                d.requestPhonemes(word,language,lambda value,error:reply.append((value,error)))
                wait(eng)
                assert reply and reply[0][0] and not reply[0][1], (language,reply)
                body = reply[0][0]
                phonemes.append(dict(language=hex(language),word=word,phonemes=body))
                for kind,text in dict(formats,phonemes=body).items():
                    eng.player.chunks.clear()
                    d.previewTool(text,kind,language)
                    wait(eng)
                    assert eng.player.samples() > 1000, (language,kind)
                    assert eng.language == d._language and tools.snapshot(d) == state
                    previews.append(dict(language=hex(language),kind=kind,samples=eng.player.samples()))
            results["phonemes"] = phonemes
            results["previews"] = previews
            for kind,text in (("phonemes","x]`v2"),("date_dmy","31/02/2026"),("ordinal","1.2.3"),("telephone","`v2")):
                try:
                    tools.annotation(text,kind,0x10000)
                    raise AssertionError("invalid annotation accepted")
                except ValueError:
                    pass
            # Copied configuration works without writes on secure screens.
            data.prepared("community_custom",eng.languages)
            copied = base.parent / "copied"
            shutil.copytree(base,copied)
            data.root = lambda: copied
            hashes = {p.relative_to(copied):hashlib.sha256(p.read_bytes()).hexdigest() for p in copied.rglob("*") if p.is_file()}
            globalVars.appArgs.secure = True
            try:
                assert "Reed – Grüße" in tools.readPresets()
                tools.applyPreset(d,"Reed – Grüße")
                wait(eng)
                assert d.dictionaryProfile == "community_custom" and not eng.dictionaryError
                for action in (lambda: tools.savePreset("no",d), lambda: tools.deletePreset("Reed – Grüße"),
                               lambda: data.saveCustom(0x40000,0,[],revision)):
                    try:
                        action()
                        raise AssertionError("secure write accepted")
                    except ValueError:
                        pass
                assert hashes == {p.relative_to(copied):hashlib.sha256(p.read_bytes()).hexdigest() for p in copied.rglob("*") if p.is_file()}
            finally:
                globalVars.appArgs.secure = False
            results["secure_readonly_copy"] = True
            results["preset_roundtrip"] = True
            assert not sequence.LOGGED["error"] and not sequence.LOGGED["warning"]
        finally:
            d.terminate()
    (args.out/"features.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print("PASS: editor/overlays/presets, 251 native WPM values, 8 phoneme languages, 56 previews, secure readonly copy")


if __name__ == "__main__":
    main()
