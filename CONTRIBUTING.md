# Contributing

Bug reports and pull requests are welcome. For a bug, include the example text, language and voice, sample rate, NVDA version, and the origin and version of the engine used. Remove personal information from logs.

Before submitting a pull request, run the tests listed in `TESTING.md` that do not require a DLL. Changes to Unicode processing and language switching should include relevant regression tests. Keep documentation, comments and interface text in English; preserve other languages where they are needed as pronunciation or Unicode test inputs.

11,025 Hz Classic remains the recommended default. Do not describe 22,050 Hz as a quality improvement without reliable new evidence. Treat interrupt-path changes separately from settings and text changes; `eciStop` and `eciDataAbort` are not safe default solutions for the engine tested here.

Do not submit DLLs, SDKs, IBM language data, extracted tables, personal dictionaries or NVDA configurations. New contributions must be compatible with this repository's MIT license. Identify the origin and license of any copied third-party source.
