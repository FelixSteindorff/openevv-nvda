# Testing

## Without an engine

```powershell
python nvda/test/sequence.py
python nvda/test/engine.py
python nvda/test/settings.py
python nvda/test/punctuation.py
python nvda/test/symbols.py
python tools/check_repository.py
```

The engine tests deliberately inject failures, including invalid sample rates and a blocked player. Related log messages are expected; check the exit code and final success message. No installed NVDA instance is modified.

## With a separately supplied OpenEVV x64 DLL

The following tests have been run with the local multilingual development DLL. That DLL is included in the downloadable test release, but not in the Git source tree. Multilingual tests expect its ten language variants; missing languages indicate a different test configuration, not automatically a driver regression.

```powershell
python nvda/test/settings.py --dll C:/my-local-path/eci.dll --out build/settings
python nvda/test/features.py --dll C:/my-local-path/eci.dll --out build/features
python nvda/test/punctuation.py --dll C:/my-local-path/eci.dll --out build/punctuation
python nvda/build.py --version 0.1.0 --dll C:/my-local-path/eci.dll
python -m zipfile -e build/openevv-0.1.0.nvda-addon build/packaged
python nvda/test/windows.py build/packaged
python nvda/test/unicode_hyphens.py --addon build/packaged --out build/hyphens
python nvda/test/unicode_text.py --addon build/packaged --out build/unicode
```

All output under `build/` is local and excluded from Git. It may contain IBM data, audio or locally configured values and is not automatically suitable for public issues or releases.

Unicode tests use separate processes for each language and spelling so that global legacy engine state cannot carry over between the reference and comparison. They check PCM equality against a defined reference, not native-speaker quality for arbitrary text. Multilingual speech samples and Unicode fixtures intentionally retain their original text even though the documentation and interface are in English.

## Documented baseline

Before this repository was separated, the local variant passed real-DLL tests for language, voice and persistence, German and English with eight voices, rapid temporary language changes, stop followed by a new utterance, and seven sample rates. Pronunciation tools passed 56 previews; 251 raw WPM values were checked against the engine. The Unicode extension passed 170 layout and typography cases and 18 PCM pair comparisons, plus ordinary German and English speech in real NVDA 2026.2 on an isolated desktop.

These results apply to a specific local DLL. Public CI checks the independently runnable Python tests; it does not download or revalidate the release engine. Interactive NVDA tests, listening tests and an actual Windows sign-in session remain separate checks.

## Release 0.1.1 verification

The final packaged add-on was extracted and tested locally before upload:

- `windows.py`: ten languages, voice names, reference PCM, index marks, repeated cancellation and recovery.
- `settings.py --dll`: German and English with eight voices, persistence, automatic language switching and restoration, 24 rapid utterances, stop followed immediately by speech, and all seven sample rates.
- `features.py --dll`: dictionary editor and overlays, presets, 251 native WPM values, eight phoneme languages, 56 previews and secure read-only copying.
- `unicode_hyphens.py`: Unicode hyphens match ASCII reference PCM in all ten language variants.
- `unicode_text.py`: 170 layout and typography fixtures, sentence boundaries, and 18 reference PCM comparisons.

All checks passed. These are automated tests using the real DLL and simulated NVDA modules. This packaging update was not retested interactively in NVDA or at Windows sign-in. The known limitations in README.md still apply.

## Release 0.1.2 verification

The packaged real DLL passed `windows.py`, `settings.py --dll`, `features.py --dll` and `unicode_text.py --addon`; the standalone sequence and engine tests also passed. Unicode coverage now includes 186 layout/typography/name fixtures and 26 reference PCM comparisons. In all eight Windows-1252 language variants, `Petr Čech` produces the same PCM as `Petr Cech` and different PCM from the former `Petr ?ech` input. Composed/decomposed spellings, supported accents and the unchanged Japanese/Polish encoding paths are checked as well.

These checks establish the character fallback, not native Czech pronunciation. No new interactive listening or Windows sign-in test was performed for this change. The engine binary is unchanged from 0.1.1.

## Release 0.1.3 verification

`punctuation.py` checks spacing around parentheses and before colons, adjacent text fragments, command boundaries, explicit spelling, retained symbol names, timestamps, URLs, line breaks, raw voice tags, and unchanged Japanese/Polish text handling. With the real DLL, 24 cases across all eight Western variants match the attached-punctuation reference PCM. German and English also differ from the old spaced-punctuation PCM; native phoneme analysis confirms the unwanted symbol names in the old input.

These tests simulate the synthesizer boundary and do not change or exercise an installed NVDA configuration. They preserve names already generated by NVDA's symbol processing. Completely isolated symbols without adjacent text, text separated by speech commands, and raw voice-tag mode are not covered by the spacing correction. No interactive listening test was performed for this change. The engine DLL is unchanged.

## Release 0.1.4 verification

`symbols.py` checks all 128 box-drawing definitions in both languages, reproducible generation, Unicode encoding, verbosity and preservation fields, and the absence of overrides for NVDA's existing arrow definitions. The repository check permits only these two reviewed text dictionaries; engine data and personal dictionaries remain excluded.

The integration test runs a separately supplied portable NVDA on a private, invisible Windows desktop with a fresh profile. It does not change or stop the user's installed NVDA. It requires the real engine in an extracted add-on:

```powershell
python nvda/test/symbols_live.py --runtime C:/my-portable-nvda/nvda.exe --addon build/packaged
```

With NVDA 2026.2 and the packaged x64 DLL, this test passed 256 localized character definitions, all four speech verbosity levels, character navigation, existing arrow names, English fallback, German/English automatic language changes and restoration, existing punctuation/math/emoji processing, and a saved personal symbol-name override. It captures both the sequence produced by NVDA and the encoded input delivered to the real engine. The supplied diagram reaches the engine without replacement question marks. This is an automated integration test, not a new listening assessment.

The optional `--secure` launch did not complete within the timeout and produced no test results. Symbol behavior on the Windows sign-in desktop is therefore not verified by this release. The engine binary and audio/interrupt paths are unchanged.

Standalone sequence, engine, settings, punctuation and symbol tests passed. Real-DLL settings tests also passed all eight German/English voices, persistence, temporary language switches and restoration, 24 rapid utterances, cancel/recovery, and all seven sample rates. Package verification confirmed that source, symbol dictionaries and license notices match the working tree and that the DLL is byte-identical to 0.1.3.
