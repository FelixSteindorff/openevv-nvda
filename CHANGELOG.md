# Changelog

## 0.1.3 - Spaced punctuation fix

- Prevent Western ECI from adding symbol names for spaced punctuation in ordinary speech: `( text )` becomes `(text)` and `Text : next` becomes `Text: next`. The punctuation itself remains available for prosody.
- Join adjacent text fragments before normalization without moving or removing speech commands.
- Preserve explicit character mode, spoken symbol names supplied by NVDA, timestamps, URLs, line breaks and raw voice-tag mode. No NVDA symbol settings are changed.
- Add standalone regressions and 24 real-DLL comparisons across the eight Western language variants. Japanese and Polish processing is unchanged.

## 0.1.2 - Latin name character fix

- Prevent unsupported, canonically decomposable Latin letters such as `Č` from becoming question marks in Windows-1252 voices. `Petr Čech` is passed to those voices as `Petr Cech`.
- Preserve directly supported letters and as many encodable accents as possible. Composed and decomposed spellings behave consistently. Japanese and Polish encoding paths are unchanged.
- Add regression coverage for names and real-DLL PCM comparisons against both the intended fallback and the previous question-mark output. This provides approximate spelling, not Czech pronunciation support.

## 0.1.1 - bundled test release

- Publish a ready-to-install x64 test add-on as a GitHub Release, with ten language variants and explicit disclosure of unresolved IBM data redistribution rights.
- Include engine provenance, preserved upstream notices and a SHA-256 checksum.
- Translate project documentation, add-on dialogs, language labels, status messages and errors into English.
- Use the English user guide for all interface languages; preserve multilingual pronunciation and Unicode test inputs.

## 0.1.0 - initial standalone source release

- NVDA variant based on OpenEVV, with separate language and voice selectors, persistence and temporary language switching.
- Classic 11,025 Hz as the default; other output rates clearly labeled.
- Dictionary management with custom corrections, an editor and preview; named presets, WPM input and expert tools.
- Support for configuration copying to secure screens.
- Normalize Unicode hyphens, layout characters and selected typographic variants before sentence splitting.
- Standalone documentation and CI without engine or IBM data. No public binary release is included in this source release.
