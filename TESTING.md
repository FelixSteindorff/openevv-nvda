# Testing

## Without an engine

```powershell
python nvda/test/sequence.py
python nvda/test/engine.py
python nvda/test/settings.py
python tools/check_repository.py
```

The engine tests deliberately inject failures, including invalid sample rates and a blocked player. Related log messages are expected; check the exit code and final success message. No installed NVDA instance is modified.

## With a separately supplied OpenEVV x64 DLL

The following tests have been run with the local multilingual development DLL. That DLL is included in the downloadable test release, but not in the Git source tree. Multilingual tests expect its ten language variants; missing languages indicate a different test configuration, not automatically a driver regression.

```powershell
python nvda/test/settings.py --dll C:/my-local-path/eci.dll --out build/settings
python nvda/test/features.py --dll C:/my-local-path/eci.dll --out build/features
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
