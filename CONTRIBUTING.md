# Beiträge

Fehlerberichte und Pull Requests sind willkommen. Beschreibe bei einem Fehler den Beispieltext, Sprache/Stimme, Sample-Rate, NVDA-Version und Herkunft/Version der verwendeten Engine. Entferne persönliche Daten aus Logs.

Vor einem Pull Request die in `TESTING.md` genannten Tests ohne DLL ausführen. Änderungen an Unicode-Verarbeitung und Sprachwechseln sollten durch entsprechende Regressionstests abgedeckt sein.

11.025 Hz Classic bleibt der empfohlene Standard. 22.050 Hz darf nicht ohne belastbaren neuen Nachweis als Qualitätsverbesserung bezeichnet werden. Änderungen am Interrupt-Pfad sind von Settings-/Textänderungen getrennt zu behandeln; `eciStop` und `eciDataAbort` sind keine sicheren Standardlösungen für die hier geprüfte Engine.

Bitte keine DLLs, SDKs, IBM-Sprachdaten, extrahierten Tabellen, persönlichen Wörterbücher oder NVDA-Konfigurationen einreichen. Neue Beiträge müssen mit der MIT-Lizenz dieses Repositorys vereinbar sein; kopierte Fremdquellen sind mit Herkunft und Lizenz zu kennzeichnen.
