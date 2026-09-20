# OpenEVV for NVDA

An extended NVDA driver based on [Mudb0y/openevv](https://github.com/Mudb0y/openevv), maintained by Felix Steindorff. It focuses on reliable controls, classic Eloquence output, pronunciation tools and Unicode handling.

**A ready-to-install test add-on, including the x64 engine and IBM-derived language data, is available under GitHub Releases. Redistribution rights for those data remain unresolved; we have not established permission to publicly redistribute them.** Publishing the package does not resolve that uncertainty. The driver's MIT license does not cover these data. Read [licensing scope](NOTICE.md) and the [engine notice](ENGINE-NOTICE.txt).

## Download and install

Download [openevv-0.1.3.nvda-addon](https://github.com/FelixSteindorff/openevv-nvda/releases/download/v0.1.3/openevv-0.1.3.nvda-addon) from the [0.1.3 test release](https://github.com/FelixSteindorff/openevv-nvda/releases/tag/v0.1.3). It includes the engine and all ten language variants listed below. No separate DLL or Python installation is needed to use it. Windows and 64-bit NVDA 2026.1 or later are required; testing used NVDA 2026.2.

Open the downloaded file in NVDA, install it, then select OpenEVV as the synthesizer. Use **11 kHz (Classic)** for the recommended output. This is a test release with the limitations listed below. The release includes a SHA-256 checksum file.

The Git source tree contains driver source, tests and documentation. Binary packages are attached to releases.

## Features

- Separate language and voice selectors; available languages are discovered from the engine.
- Eight classic voices with stable IDs: Reed, Shelley, Sandy, Rocko, Glen, FastFlo, Grandma, Grandpa.
- Persistent settings; automatic language changes preserve the voice and return to the default language.
- **11 kHz (Classic)** as the recommended default. 22 kHz is explicitly labeled **Experimental**; 16/32/44.1/48 kHz are **Resampled**. Enhanced remains disabled.
- Rate, pitch, pitch range, volume, rate boost, head size, roughness and breathiness controls.
- Optional pronunciation dictionaries with an editor, preview and custom corrections layered over Community or Alternative files.
- Named voice presets, WPM input, phoneme analysis and number previews.
- Normalize spacing around parentheses and before colons in ordinary Western-language speech so that retained punctuation supplies prosody instead of extra symbol names. Explicit spelling and raw voice-tag mode are preserved.
- Handling of Unicode hyphens, layout characters and unsupported typographic variants, including consistent sentence splitting. Unsupported Latin letters with canonical accent decompositions use an encodable approximation in Western voices (for example, Petr Čech becomes Petr Cech), instead of a question mark. Supported accents are preserved; this is not a guarantee of native-language pronunciation.
- Support for NVDA's configuration copy for sign-in and secure screens; downloads and file management are disabled there.

Local development was tested with a Windows x64 engine containing ten language variants: American and British English, German, Spanish (Spain and Latin America), French (France and Canada), Italian, and experimental Japanese and Polish. The published test package includes this engine. For custom builds, the supplied DLL determines which languages are available. Phoneme analysis and special pronunciation tools support the eight Western variants.

## Building from source

- Windows and **64-bit NVDA**; tested with NVDA 2026.2.
- Python 3.11 or later for building and testing.
- A separately supplied, compatible **OpenEVV x64 `eci.dll`**, with appropriate usage rights. Other Eloquence builds are not automatically compatible. This repository does not download an engine or build IBM data.

```powershell
python nvda/build.py --version 0.1.3 --dll C:/my-local-path/eci.dll --engine-notice ENGINE-NOTICE.txt
```

The build checks the architecture and required ECI exports, then creates `build/openevv-0.1.3.nvda-addon`. Passing the export check does not establish full compatibility; tests with the real DLL are still required. The supplied engine is included in the local package. **This does not grant additional rights to redistribute the resulting package.** The example includes `ENGINE-NOTICE.txt` for our tested engine. When supplying a different DLL, provide its corresponding provenance and license notices with `--engine-notice PATH`.

Install the package in NVDA and select OpenEVV as the speech synthesizer. Save settings with **NVDA+Control+C** as needed. The package retains the internal name `openevv`, so it updates existing OpenEVV test installations rather than installing a second synthesizer.

See the [user guide](nvda/addon/doc/en/readme.html) for detailed instructions. Its language descriptions refer to the engine included in the test release. Documentation and add-on-specific interface text are in English. Multilingual pronunciation and Unicode test inputs intentionally retain their original languages.

## Tests

Without an engine DLL, including in GitHub Actions:

```powershell
python nvda/test/sequence.py
python nvda/test/engine.py
python nvda/test/settings.py
python nvda/test/punctuation.py
python tools/check_repository.py
```

[TESTING.md](TESTING.md) describes additional tests using a compatible DLL supplied locally. These use simulated NVDA modules and captured PCM. They do not replace listening tests or interactive NVDA testing. Public CI runs do not download an engine or publish binary packages. Release packages are built and tested locally, then uploaded separately.

## Known limitations

- Native 22,050 Hz synthesis has no demonstrated overall quality advantage over Classic 11,025 Hz. The original output remains recommended.
- The reported quiet background noise during resampling and rapid navigation has not been conclusively verified as resolved.
- Japanese has known native failures with certain control sequences; the driver filters raw text tags for that language. Polish remains incomplete. Both are experimental.
- Legacy encodings cannot represent every Unicode character. NVDA's symbol processing and the correct language selection remain important.
- An actual Windows sign-in session has not been tested. Testing covered an isolated NVDA instance in secure mode and configuration copying to a test destination.

## Origin and contributions

The starting point is OpenEVV commit `0f2c8fad08c4fbfd1364b14993e3ccdcfcf9e6b6`, with locally developed NVDA changes through the Unicode test build of September 19, 2026. This repository starts a separate driver history and does not import engine or SDK history.

Please include the NVDA version, Windows and engine versions, language, voice, sample rate and a minimal example in bug reports. Do not upload private NVDA configurations, language data or commercial DLLs. See [CONTRIBUTING.md](CONTRIBUTING.md).
