#!/usr/bin/env python3
"""Settings-dialog/config simulation, optionally through the real Windows DLL.

python nvda/test/settings.py --dll build/hq/eci-enus-dede-c.dll
No NVDA installation/configuration is changed; the player records PCM.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import unicodedata

import sequence


def wait(engine):
    deadline = time.monotonic() + 20
    while engine._work.unfinished_tasks:
        if time.monotonic() > deadline:
            raise AssertionError("engine queue did not drain")
        time.sleep(.005)


def simulated():
    sequence._install_stubs()
    sys.path.insert(0, sequence.ADDON)
    import config
    from synthDrivers import _openevv as e, openevv as driver
    original = e.Engine
    e.Engine = sequence.FakeEngine
    sequence.FakeEngine.languages = list(e.LANGUAGE_NAMES)
    # NVDA's base loads voice first, then settings in declaration order.
    # ConfigParser isn't required to test the order or round-trip values.
    def load(self, onlyChanged=False):
        c = config.conf["speech"]["openevv"]
        if not onlyChanged or self.voice != c["voice"]:
            self.voice = c["voice"]
        for s in self.supportedSettings:
            if s.useConfig and s.id != "voice" and c.get(s.id) is not None:
                if onlyChanged and getattr(self, s.id) == c[s.id]:
                    continue
                setattr(self, s.id, c[s.id])
    def save(self):
        config.conf["speech"]["openevv"] = {s.id: getattr(self, s.id) for s in self.supportedSettings}
    sequence._SynthDriver.loadSettings = load
    sequence._SynthDriver.saveSettings = save
    sequence._SynthDriver._configSection = "speech"
    try:
        d = driver.SynthDriver()
        ids = [s.id for s in d.supportedSettings]
        assert ids == ["language", "voice", "rate", "pitch", "inflection", "volume",
                       "rateBoost", "headSize", "roughness", "breathiness",
                       "abbreviations", "voiceTags", "dictionaryProfile", "samplerate"]
        assert d.samplerate == "11025"
        assert d.supportedSettings[-1].defaultVal == "11025"
        for lang in d.availableLanguages:
            d.language = lang
            assert len(d.availableVoices) == 8
            assert d.availableVoices["1"].name == "Reed"
            assert len({v.name for v in d.availableVoices.values()}) == 8
            for name in [v.displayName for v in d.availableLanguages.values()]:
                assert isinstance(name, str)
                assert not any(bad in name for bad in ("Ã", "Â", "\ufffd"))
        assert d.availableLanguages["de_DE"].displayName == "German"
        assert d.availableLanguages["fr_FR"].displayName == "French"
        # Unrepresentable Latin accents in names must not become spoken '?'.
        for language in e.LOCALES:
            codec = e.encodingOf(language)
            for source_text, fallback in (("Petr \u010cech", "Petr Cech"),
                                       ("Petr C\u030cech", "Petr Cech"),
                                       ("\u0106ori\u0107", "Coric"),
                                       ("\u01d8", "\u00fc")):
                expected = fallback if codec == "cp1252" else unicodedata.normalize("NFC", source_text)
                assert e.encodeText(source_text, language) == expected.encode(codec, "replace")
            native = "\u00e4\u00e9\u0160\u017d?"
            assert e.encodeText(native, language) == native.encode(codec, "replace")
        umlauts = "äöüÄÖÜß"
        assert e.encodeText(umlauts, 0x40000) == b"\xe4\xf6\xfc\xc4\xd6\xdc\xdf"
        assert e.decodeName(umlauts.encode("cp1252"), 0x40000) == umlauts
        assert e.decodeName("日本語".encode("cp932"), 0x80000) == "日本語"
        assert e.decodeName("Głos".encode("utf-8"), 0x110000) == "Głos"
        assert e.encodeText(unicodedata.normalize("NFD", umlauts), 0x40000) == e.encodeText(umlauts, 0x40000)
        assert e.encodeText("cafe\u0301", 0x10000) == b"caf\xe9"
        assert e.encodeText("12\u202fkm", 0x40000) == b"12 km"
        assert e.encodeText("12\u2009km", 0x40000) == b"12 km"
        assert e.encodeText("\u3000", 0x80000) == "\u3000".encode("cp932")
        assert e.encodeText("\u00a0", 0x40000) == b"\xa0"
        for language in e.LOCALES:
            for hyphen in ("\u2010", "\u2011"):
                assert e.encodeText(f"THE{hyphen}DECODER{hyphen}Abo?", language) == b"THE-DECODER-Abo?"
        # Representable punctuation is not flattened along with hyphens.
        assert e.encodeText("– — ?", 0x40000) == "– — ?".encode("cp1252")
        assert e.encodeText("日本語", 0x80000) == "日本語".encode("cp932")
        assert e.encodeText("Zażółć", 0x110000) == "Zażółć".encode("utf-8")
        # ctypes output buffer, not a Python string passed through unchanged.
        class NamesDll:
            def eciGetVoiceName(self, handle, number, room):
                room.value = ("Grüße " + umlauts).encode("cp1252")
                return 1
        real = original(lambda i: None)
        real._dll, real._instance, real.language = NamesDll(), 1, 0x40000
        assert all(name == "Grüße " + umlauts for name in real._voiceNames().values())
        config.conf["speech"] = {"openevv": {}}
        d.language, d.voice, d.samplerate = "de_DE", "4", "22050"
        values = dict(rate=73, pitch=62, inflection=41, volume=87, rateBoost=True,
                      headSize=58, roughness=23, breathiness=17,
                      abbreviations=True, voiceTags=True)
        for name, value in values.items():
            setattr(d, name, value)
        controls = len(d._engine.calls)
        for _ in range(1000):
            d.pitch = values["pitch"]
        assert len(d._engine.calls) == controls
        d.saveSettings()
        saved = json.loads(json.dumps(config.conf["speech"]["openevv"]))
        d.terminate()
        d = driver.SynthDriver()
        config.conf["speech"]["openevv"] = saved
        d.loadSettings()
        assert (d.language, d.voice, d.samplerate) == ("de_DE", "4", "22050")
        assert all(getattr(d, name) == value for name, value in values.items())
        d.saveSettings()
        assert config.conf["speech"]["openevv"] == saved
        for percent in range(101):
            d.rate = percent
            assert d.rate == percent  # no round-trip quantisation in the UI
        config.conf["speech"]["openevv"] = saved
        d.loadSettings(onlyChanged=True)
        assert all(getattr(d, name) == value for name, value in values.items())
        config.conf["speech"]["openevv"] = {"voice": "262144:2", "samplerate": "44100"}
        d.loadSettings()
        assert (d.language, d.voice, d.samplerate) == ("de_DE", "2", "44100")
        assert config.conf["speech"]["openevv"]["voice"] == "2"
        config.conf["speech"]["openevv"] = {"language": "xx", "voice": "999", "samplerate": "3"}
        d.loadSettings()
        assert (d.language, d.voice, d.samplerate) == ("en_US", "1", "11025")
        for name in ("language", "voice", "samplerate"):
            assert config.conf["speech"]["openevv"][name] == getattr(d, name)
        for malformed in (None, "invalid", [], {}, float("nan")):
            config.conf["speech"]["openevv"] = {name: malformed for name in ids}
            d.loadSettings()
            assert (d.language, d.voice, d.samplerate) == ("en_US", "1", "11025")
            assert all(0 <= getattr(d, name) <= 100 for name in values if name not in (
                "rateBoost", "abbreviations", "voiceTags"))
        d.samplerate = "22050"
        config.conf["speech"]["openevv"] = {}
        d.loadSettings()
        assert d.samplerate == "11025"
        assert list(d.availableSamplerates) == ["8000", "11025", "16000", "22050", "32000", "44100", "48000"]
        assert d.availableSamplerates["22050"].displayName == "22 kHz (Experimental)"
        for hz in ("8000", "11025", "22050", "16000", "32000", "44100", "48000"):
            d.samplerate = hz
            assert d.samplerate == hz
            if hz not in ("8000", "11025", "22050"):
                assert "Resampled" in d.availableSamplerates[hz].displayName
        # A future library may omit a preset: manual switching must select a
        # valid ID without generating a combined language/voice entry.
        d.language, d.voice = "en_US", "8"
        del d._engine.voiceNamesByLanguage[0x40000][8]
        d.language = "de_DE"
        assert d.voice == "1" and "8" not in d.availableVoices
        print("PASS: Unicode labels/umlauts, separate ordered settings, 8 presets, full persistence, legacy migration, invalid/missing settings, all rates, missing voice fallback")
    finally:
        e.Engine = original
        sequence.FakeEngine.languages = [0x10000]
    return e, driver


def real_dll(path, e, driver, out):
    import nvwave
    from windows import WavePlayer
    nvwave.WavePlayer = WavePlayer
    e.libraryPath = lambda: str(Path(path).resolve())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    def synth(text, encoding=None):
        d = driver.SynthDriver()
        try:
            assert 0x40000 in d._engine.languages and 0x10000 in d._engine.languages
            d.language = "de_DE"
            wait(d._engine)
            if encoding:
                d._engine.post([(d._engine.addText, (text.encode(encoding),)),
                                (d._engine.synthesize, (True,))])
            else:
                d.speak([text])
            wait(d._engine)
            return b"".join(d._engine.player.chunks)
        finally:
            d.terminate()
    results = []
    for text in ("ä", "ö", "ü", "Ä", "Ö", "Ü", "ß", "Grüße, größer, schön, fünf. Äpfel, Öl und Übermut."):
        corrected = synth(text)
        native = synth(text, "cp1252")
        broken = synth(text, "utf-8")
        assert corrected == native and len(corrected) > 0
        assert broken != corrected, repr(text)
        results.append(dict(text=text, samples=len(corrected) // 2,
                            corrected_sha256=hashlib.sha256(corrected).hexdigest(),
                            old_utf8_sha256=hashlib.sha256(broken).hexdigest(),
                            equals_cp1252=True))
    (out / "unicode-dll.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    normalization = []
    for native, equivalent in (("äöüÄÖÜß", unicodedata.normalize("NFD", "äöüÄÖÜß")),
                               ("café", "cafe\u0301"), ("12 km", "12\u202fkm")):
        a, b = synth(native), synth(equivalent)
        assert a == b and a
        normalization.append(dict(reference=native, input=equivalent, pcm_equal=True,
                                  sha256=hashlib.sha256(a).hexdigest()))
    (out / "unicode-normalization.json").write_text(json.dumps(normalization, ensure_ascii=False, indent=2), encoding="utf-8")
    d = driver.SynthDriver()
    try:
        for lang in ("de_DE", "en_US", "de_DE"):
            d.language = lang
            d.voice = "2"
            for hz in ("22050", "8000", "11025"):
                d.samplerate = hz
                d.speak(["Test."])
                wait(d._engine)
                assert d._engine.sampleRate == int(hz)
                assert d._engine.language == (0x40000 if lang == "de_DE" else 0x10000)
                assert d._engine.player.samples() > 0
        d.language = "en_US"
        d.rate = 60
        wait(d._engine)
        params = dict(d._engine.voiceParams)
        d.speak(["Hello.", sequence.LangChangeCommand("de"), "Grüße."])
        wait(d._engine)
        assert d.language == "en_US" and d._engine.language == 0x10000
        assert params == d._engine.voiceParams
        d.cancel()
        d.speak(["Hello again."])
        wait(d._engine)
        assert d._engine.language == 0x10000 and d.voice == "2"
        d.speak([sequence.LangChangeCommand("de"), "Grüße.", sequence.LangChangeCommand(None), "Hello."])
        wait(d._engine)
        assert d._engine.language == 0x10000
    finally:
        d.terminate()
    print("PASS: real DLL, all 7 umlauts match cp1252 PCM and differ from old UTF-8; language/voice/rate switches; automatic switching, cancel recovery")
    real_matrix(e, driver, out)


def real_matrix(e, driver, out):
    """Exercise selected state independently of the actual DLL worker state."""
    config = driver.config
    records = []
    def selected(d):
        return {s.id: getattr(d, s.id) for s in d.supportedSettings}

    d = driver.SynthDriver()
    try:
        assert d.samplerate == "11025" and d._engine.sampleRate == 11025
        assert ctypes.sizeof(ctypes.c_void_p) == 8
        assert {"en_US", "de_DE"} <= set(d.availableLanguages)
        engine = d._engine
        trace, copies = [], []
        select_language, copy_voice = engine.selectLanguage, engine.copyVoice
        def copy(number):
            copies.append((engine.language, number))
            return copy_voice(number)
        def select(language, preset):
            select_language(language, preset)
            trace.append(dict(language=engine._dll.eciGetParam(engine._instance, e.PARAM_LANGUAGE),
                              preset=preset, selected=selected(d),
                              params={k: engine.getVoiceParam(k) for k in e.VOICE_RANGE}))
        engine.copyVoice, engine.selectLanguage = copy, select
        for language, other, text, translation in (
            ("de_DE", "en_US", "Grüße, schön und deutlich.", "A clear English sentence."),
            ("en_US", "de_DE", "A clear English sentence.", "Grüße, schön und deutlich."),
        ):
            default_id = next(k for k in engine.languages if e.localeOf(k) == language)
            other_id = next(k for k in engine.languages if e.localeOf(k) == other)
            hashes = []
            for voice in range(1, 9):
                d.language, d.voice = language, str(voice)
                wait(engine)
                state, params = selected(d), dict(engine.voiceParams)
                assert params == d._voiceParams
                engine.player.chunks.clear()
                d.speak([text])
                wait(engine)
                assert engine.player.samples() > 0
                digest = engine.player.digest()
                hashes.append(digest)
                trace.clear()
                copies.clear()
                d.speak([text, sequence.LangChangeCommand(other), translation])
                wait(engine)
                assert [t["language"] for t in trace] == [default_id, other_id, default_id]
                assert copies == [(other_id, voice), (default_id, voice)]
                assert all(t["selected"] == state and t["params"] == params for t in trace)
                assert selected(d) == state and engine.voiceParams == params
                records.append(dict(language=language, voice=voice, name=d.availableVoices[str(voice)].name,
                                    sample_rate=engine.sampleRate, pcm_sha256=digest,
                                    automatic_languages=[t["language"] for t in trace],
                                    copies=list(copies), restored=True))
                # Explicit None, dialect matching, and unsupported-language fallback.
                d.speak([sequence.LangChangeCommand(other.replace("_", "-")), translation,
                         sequence.LangChangeCommand("xx"), translation,
                         sequence.LangChangeCommand(None), text])
                wait(engine)
                assert engine.language == default_id and selected(d) == state
            assert len(set(hashes)) == 8, "preset choice must change the actual PCM"

            # Several utterances queued without waiting, each independently restored.
            trace.clear()
            for _ in range(12):
                d.speak([sequence.LangChangeCommand(other), translation])
            wait(engine)
            assert [t["language"] for t in trace] == [default_id, other_id, default_id] * 12
            assert selected(d) == state

            # Stop while a buffer is in flight, then immediately enqueue new speech.
            # Only the recording player's pacing is controlled; the real ECI path
            # and the driver's existing cancel implementation are left intact.
            entered, released = threading.Event(), threading.Event()
            player = engine.player
            feed, stop = player.feed, player.stop
            def blocking_feed(*args, **kwargs):
                feed(*args, **kwargs)
                if not entered.is_set():
                    entered.set()
                    assert released.wait(10), "test player was not stopped"
            def releasing_stop():
                stop()
                released.set()
            player.feed, player.stop = blocking_feed, releasing_stop
            try:
                d.speak([sequence.LangChangeCommand(other), translation * 100,
                         sequence.LangChangeCommand(None), text])
                assert entered.wait(10)
                d.cancel()
                before = player.samples()
                d.speak([text])
                wait(engine)
                assert player.stopped > 0 and player.samples() > before
                assert engine.language == default_id and selected(d) == state
            finally:
                released.set()
                player.feed, player.stop = feed, stop

        # Unavailable temporary preset: retain manual ID 8, copy fallback ID 1.
        d.language, d.voice = "en_US", "8"
        wait(engine)
        # Inject limited metadata: the current DLL itself has all eight.
        names = engine._voiceNames
        def limited_names(language=None):
            available = names(language)
            if (engine.language if language is None else language) == 0x40000:
                available.pop(8, None)
            return available
        engine._voiceNames = limited_names
        copies.clear()
        d.speak([sequence.LangChangeCommand("de"), "Hallo."])
        wait(engine)
        assert copies == [(0x40000, 1), (0x10000, 8)] and d.voice == "8"
        engine._voiceNames = names

        # Simulate saving immediately while previous work still holds the worker.
        entered, released = threading.Event(), threading.Event()
        def hold():
            entered.set()
            assert released.wait(10)
        engine.control([(hold, ())])
        assert entered.wait(10)
        try:
            d.language, d.voice, d.samplerate = "de_DE", "4", "11025"
            d.rateBoost = True
            custom = dict(rate=73, pitch=61, inflection=42, volume=86, headSize=59,
                          roughness=22, breathiness=16, abbreviations=True, voiceTags=True)
            for key, value in custom.items():
                setattr(d, key, value)
            queued = engine._work.qsize()
            for _ in range(2000):
                d.pitch = custom["pitch"]
            assert engine._work.qsize() == queued
            d.saveSettings()
            saved = json.loads(json.dumps(config.conf["speech"]["openevv"]))
            assert saved == selected(d)
            assert all(saved[key] == value for key, value in custom.items())
        finally:
            released.set()
        wait(engine)
        assert engine.voiceParams == d._voiceParams
        engine.control([(lambda: records.append(dict(persistence_raw_params={
            k: engine.getVoiceParam(k) for k in e.VOICE_RANGE})), ())])
        wait(engine)
        assert records[-1]["persistence_raw_params"] == d._voiceParams
    finally:
        d.terminate()

    d = driver.SynthDriver()
    try:
        config.conf["speech"]["openevv"] = saved
        d.loadSettings()
        assert selected(d) == saved  # immediately, before the worker catches up
        wait(d._engine)
        assert d._engine.voiceParams == d._voiceParams
        for hz in d.availableSamplerates:
            d.samplerate = hz
            d.speak(["Test."])
            wait(d._engine)
            assert d._engine.sampleRate == int(hz) and d._engine.player.samples() > 0
        d.samplerate = "invalid"
        d.speak(["Classic."])
        wait(d._engine)
        assert d.samplerate == "11025" and d._engine.sampleRate == 11025
        assert not sequence.LOGGED["error"]
        assert not sequence.LOGGED["warning"]
    finally:
        d.terminate()
    (out / "real-dll-matrix.json").write_text(json.dumps(dict(
        dll_sha256=hashlib.sha256(Path(e.libraryPath()).read_bytes()).hexdigest(),
        cases=records, persisted_settings=saved, fast_switch_utterances=24,
        stop_and_immediate_speech_both_directions=True, all_seven_rates=True),
        indent=2, ensure_ascii=False), encoding="utf-8")
    print("PASS: real x64 DLL: DE/EN x 8 distinct voices, transient switches/restoration, 24 rapid utterances, voice fallback, stop/immediate speech both ways, queued-settings save/reopen, all 7 rates")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll")
    ap.add_argument("--addon", help="test an extracted package instead of source")
    ap.add_argument("--out", default="build/nvda-final-tests")
    args = ap.parse_args()
    if args.addon:
        sequence.ADDON = str(Path(args.addon).resolve())
    e, d = simulated()
    if args.dll:
        real_dll(args.dll, e, d, args.out)
