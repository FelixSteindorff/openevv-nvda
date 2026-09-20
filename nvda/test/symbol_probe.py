"""Test-only plugin for symbols_live.py; never packaged in the add-on."""
import json
from pathlib import Path
import traceback

import characterProcessing as cp
import config
import core
import globalPluginHandler
import globalVars
import speech
from speech.commands import LangChangeCommand
import synthDriverHandler
import wx

DIAGRAM = ("feat/openclaw-v4  \u2500\u2510\n"
           "chore/install-script \u2500\u253c\u2500\u2192  local: integration   (bauen & auf dem iPhone testen)\n"
           "docs/accessibility \u2500\u2518")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self.root = Path(globalVars.appArgs.configPath)
        self.rows = []
        self.timer = wx.CallLater(2200, self.start)

    def finish(self, error=None):
        data = dict(error=error, rows=self.rows, secure=globalVars.appArgs.secure)
        (self.root / "symbol-results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        wx.CallAfter(core.triggerNVDAExit)

    def start(self):
        try:
            import buildVersion
            assert synthDriverHandler.setSynth("openevv")
            self.d = synthDriverHandler.getSynth()
            self.d.volume = 0
            self.d.rate = 80
            self.d.voiceTags = False
            self.d.dictionaryProfile = "builtin"
            config.conf["speech"]["trustVoiceLanguage"] = True
            config.conf["speech"]["symbolLevel"] = 0
            config.conf["speech"]["autoLanguageSwitching"] = True
            definitions = cp.listAvailableSymbolDictionaryDefinitions()
            found = [d for d in definitions if d.name == "openevv"]
            assert len(found) == 1 and found[0].enabled and found[0].mandatory
            self.rows.append(dict(nvda=buildVersion.version, definition_registered=True))
            for locale in ("de", "en"):
                for number in range(0x2500, 0x2580):
                    char = chr(number)
                    name = cp.processSpeechSymbol(locale, char)
                    assert name != char and name.strip(), (locale, hex(number))
                    assert char not in cp.processSpeechSymbols(locale, char, cp.SymbolLevel.ALL)
                    for level in (cp.SymbolLevel.NONE, cp.SymbolLevel.SOME, cp.SymbolLevel.MOST):
                        assert not cp.processSpeechSymbols(locale, char, level).strip(), (locale, number, level)
            assert cp.processSpeechSymbol("de", "\u2192") == "Pfeil nach rechts"
            assert cp.processSpeechSymbol("en", "\u2192") == "right arrow"
            assert cp.processSpeechSymbol("fr", "\u2510") == "top right corner"
            self.rows.append(dict(symbols_checked=256, lower_levels_silent=True, existing_arrow_names=True,
                                  english_fallback=True))
            self.encoded, self.sequences = [], []
            add = self.d._engine.addText
            def capture(text):
                self.encoded.append(text.hex())
                return add(text)
            self.d._engine.addText = capture
            speak = self.d.speak
            def capture_sequence(seq):
                self.sequences.append([item if isinstance(item, str) else type(item).__name__ for item in seq])
                return speak(seq)
            self.d.speak = capture_sequence
            self.cases = []
            for locale in ("de_DE", "en_US"):
                for level in (cp.SymbolLevel.NONE, cp.SymbolLevel.SOME, cp.SymbolLevel.MOST, cp.SymbolLevel.ALL):
                    self.cases.append((locale, level, "diagram"))
                self.cases.append((locale, cp.SymbolLevel.CHAR, "character"))
                self.cases.append((locale, cp.SymbolLevel.ALL, "switch"))
                self.cases.append((locale, cp.SymbolLevel.ALL, "unicode"))
            self.timer = wx.CallLater(100, self.next_case)
        except Exception:
            self.finish(traceback.format_exc())

    def next_case(self):
        try:
            if not self.cases:
                # Override via NVDA's own API, saving only to this isolated
                # profile. Reload checks persistence and user precedence.
                processor = cp._localeSpeechSymbolProcessors.fetchLocaleData("de")
                custom = cp.SpeechSymbol("\u253c", replacement="Mein Kreuz", level=cp.SymbolLevel.ALL,
                                         preserve=cp.SYMPRES_NEVER)
                processor.updateSymbol(custom)
                processor.userSymbols.save(processor.userSymbols.fileName)
                cp.clearSpeechSymbols()
                assert cp.processSpeechSymbol("de", "\u253c") == "Mein Kreuz"
                assert "Mein Kreuz" in cp.processSpeechSymbols("de", "\u253c", cp.SymbolLevel.ALL)
                assert not cp.processSpeechSymbols("de", "\u253c", cp.SymbolLevel.NONE).strip()
                self.rows.append(dict(user_override_persisted=True))
                self.finish()
                return
            self.case = self.cases.pop(0)
            locale, level, mode = self.case
            speech.cancelSpeech()
            self.d.language = locale
            self.encoded.clear()
            self.sequences.clear()
            if mode == "character":
                speech.speakSpelling("\u2510")
            else:
                seq = [DIAGRAM]
                if mode == "switch":
                    target = "en_US" if locale == "de_DE" else "de_DE"
                    seq = ["Test \u2510", LangChangeCommand(target), "Test \u2518", LangChangeCommand(None), "Test \u253c"]
                elif mode == "unicode":
                    seq = ["Test 5 \u2212 3 = 2. A \u2192 B. \U0001f600. Petr \u010cech? 12:30."]
                speech.speak(seq, symbolLevel=level)
            self.attempts = 0
            self.timer = wx.CallLater(100, self.check_case)
        except Exception:
            self.finish(traceback.format_exc())

    def check_case(self):
        try:
            self.attempts += 1
            if self.d._engine._work.unfinished_tasks or not self.sequences:
                assert self.attempts < 400, (self.case, "speech timed out")
                self.timer = wx.CallLater(50, self.check_case)
                return
            locale, level, mode = self.case
            text = " ".join(item for seq in self.sequences for item in seq if isinstance(item, str))
            encoded = b"".join(bytes.fromhex(value) for value in self.encoded).decode("cp1252")
            assert self.encoded, self.case
            assert not any(0x2500 <= ord(c) <= 0x257f for c in text), (self.case, text)
            if mode != "unicode":
                assert "?" not in encoded, (self.case, encoded)
            name = "Rahmenecke oben rechts" if locale == "de_DE" else "top right corner"
            if mode == "diagram":
                assert (name in text) == (level == cp.SymbolLevel.ALL), (self.case, text)
                arrow = "Pfeil nach rechts" if locale == "de_DE" else "right arrow"
                assert (arrow in text) == (level >= cp.SymbolLevel.SOME), (self.case, text)
            elif mode == "character":
                assert name in text, (self.case, text)
            elif mode == "switch":
                assert "Rahmenecke" in text and "corner" in text, text
                assert self.d.language == locale
                from synthDrivers import _openevv
                assert self.d._engine.language == self.d._language
            elif mode == "unicode":
                assert "Petr Cech" in encoded and "12" in encoded and "30" in encoded, encoded
                assert "question" in text.lower() or "frage" in text.lower(), text
            self.rows.append(dict(locale=locale, level=int(level), mode=mode, text=text, encoded=encoded))
            self.timer = wx.CallLater(100, self.next_case)
        except Exception:
            self.finish(traceback.format_exc())

    def terminate(self):
        if self.timer:
            self.timer.Stop()
