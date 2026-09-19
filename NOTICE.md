# Origin and licensing scope

The driver, build and test sources in this repository are based on the NVDA directory of [Mudb0y/openevv](https://github.com/Mudb0y/openevv), copyright 2026 Stanislaw Przedzinkowski, licensed under MIT. This extended variant is maintained by Felix Steindorff. The original copyright and license notices are preserved in `LICENSE`.

This repository contains **no OpenEVV engine DLL, reconstructed native engine sources, IBM language modules, synthesis tables or IBM SDK**. This repository's MIT license grants no rights to those components.

The original OpenEVV project distinguishes its own work from language data and tables originating from IBM Embedded ViaVoice: see the [upstream NOTICE](https://github.com/Mudb0y/openevv/blob/main/NOTICE). IBM language data does not become MIT-licensed merely because it appears in a GitHub repository or in a newly compiled DLL.

Review of the original Embedded ViaVoice 4.3 SDK (October 2004, AT2T5ZZ) found redistribution permission for sample programs, but no general authorization to modify and publicly redistribute the language data or runtime libraries built from it. The SDK documentation refers to separate IBM agreements for the product. A complete product-specific license agreement was not located. This describes the research findings; it is not binding legal advice or a definitive assessment of all possible usage rights.

A local build using `--dll` includes the user-supplied library in the add-on. Users must establish the rights required to obtain, use and, where applicable, redistribute that library. A successful technical check or a license notice does not substitute for those rights. CI does not download or distribute an engine.

Optional additional dictionaries come from [AltIBMTTSDictionaries](https://github.com/mohamed00/AltIBMTTSDictionaries) and [IBMTTSDictionaries](https://github.com/eigencrow/IBMTTSDictionaries). They are downloaded separately only on request, are not part of this repository and retain their respective license terms. The driver's MIT license does not relicense those files.

OpenEVV, IBM, ViaVoice, Eloquence and NVDA refer to their respective projects or products. This repository is an independent development and does not claim official endorsement by their providers.
