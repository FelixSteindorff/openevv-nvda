# OpenEVV für NVDA

Weiterentwickelter NVDA-Treiber auf Basis von [Mudb0y/openevv](https://github.com/Mudb0y/openevv), gepflegt von Felix Steindorff. Schwerpunkt sind zuverlässige Bedienung, klassische Eloquence-Ausgabe, Aussprachewerkzeuge und Unicode-Verarbeitung.

**Dieses Repository enthält ausschließlich den Add-on-Quellcode, Tests und Dokumentation. Eine Engine-DLL, IBM-Sprachdaten oder ein sofort sprechendes Installationspaket sind nicht enthalten.** Die Weitergaberechte an den aus dem IBM-SDK übernommenen Bestandteilen sind nicht geklärt. Sie fallen nicht unter die MIT-Lizenz dieses Treibers. Siehe [Lizenzumfang](NOTICE.md).

## Funktionen

- Sprache und Stimme getrennt auswählen; verfügbare Sprachen werden aus der Engine ermittelt.
- Acht klassische Stimmen mit stabilen IDs: Reed, Shelley, Sandy, Rocko, Glen, FastFlo, Grandma, Grandpa.
- Persistente Einstellungen; automatische Sprachwechsel behalten die Stimme und kehren zur Standardsprache zurück.
- **11 kHz (Classic)** als Standard und Empfehlung. 22 kHz heißt ausdrücklich **Experimental**; 16/32/44,1/48 kHz sind **Resampled**. Enhanced bleibt deaktiviert.
- Geschwindigkeit, Tonhöhe, Tonhöhenumfang, Lautstärke, Geschwindigkeitsanhebung, Kopfgröße, Rauheit und Behauchtheit.
- Optionale Aussprachewörterbücher mit Editor, Vorschau und eigenen Korrekturen zusätzlich zu Community-/Alternative-Dateien.
- Benannte Stimmen-Presets, WPM-Eingabe sowie Phonetik- und Zahlenvorschau.
- Korrekturen für Unicode-Bindestriche, Layoutzeichen und nicht darstellbare typografische Varianten, einschließlich konsistenter Satzaufteilung.
- Unterstützung von NVDAs Konfigurationskopie für Anmeldung und sichere Bildschirme; dort keine Downloads oder Dateiverwaltung.

Die lokale Entwicklung wurde mit einer Windows-x64-Engine mit zehn Sprachvarianten getestet: US-/UK-Englisch, Deutsch, Spanien-/Lateinamerika-Spanisch, Frankreich-/Kanada-Französisch, Italienisch sowie experimentell Japanisch und Polnisch. **Welche davon tatsächlich auswählbar sind, bestimmt die separat bereitgestellte DLL.** Phonetik und spezielle Aussprachewerkzeuge unterstützen die acht westlichen Varianten.

## Voraussetzungen und lokaler Build

- Windows und **64-Bit-NVDA**; tatsächlich getestet mit NVDA 2026.2.
- Python 3.11 oder neuer zum Bauen und Testen.
- Eine separat und mit passenden Rechten bereitgestellte, kompatible **OpenEVV-x64-`eci.dll`**. Ein beliebiger anderer Eloquence-Build ist nicht automatisch kompatibel. Dieses Repository lädt keine Engine herunter und baut keine IBM-Daten.

```powershell
python nvda/build.py --version 0.1.0 --dll C:/mein-lokaler-pfad/eci.dll
```

Der Build prüft Architektur und benötigte ECI-Exporte und erzeugt `build/openevv-0.1.0.nvda-addon`. Erfolgreiche Exportprüfung belegt noch nicht die vollständige Kompatibilität; die Tests mit echter DLL bleiben erforderlich. Die lokal eingebundene Engine wird in dieses Paket aufgenommen. **Das gibt keine zusätzlichen Rechte, das fertige Paket weiterzugeben.** Zusätzliche Herkunfts-/Lizenztexte der Engine können mit `--engine-notice PFAD` beigefügt werden.

Das Paket in NVDA installieren und OpenEVV als Sprachausgabe wählen. Einstellungen nach Bedarf mit **NVDA+Strg+C** speichern. Es verwendet den bisherigen internen Namen `openevv` und aktualisiert daher vorhandene OpenEVV-Testinstallationen, statt einen zweiten Synthesizer einzurichten.

Die ausführliche Bedienung steht in der [deutschen Hilfe](nvda/addon/doc/de/readme.html) und der [English help](nvda/addon/doc/en/readme.html). Die Sprachangaben dort beschreiben die lokal getestete Engine-Konfiguration; das öffentliche Repository liefert diese Engine nicht mit.

## Tests

Ohne Engine-DLL, auch in GitHub Actions:

```powershell
python nvda/test/sequence.py
python nvda/test/engine.py
python nvda/test/settings.py
python tools/check_repository.py
```

Zusätzliche Tests mit eigener kompatibler DLL sind in [TESTING.md](TESTING.md) beschrieben. Diese verwenden simulierte NVDA-Module und aufgezeichnetes PCM. Sie ersetzen keinen Hörtest oder interaktiven Test mit NVDA. Die öffentlichen CI-Läufe laden keine Engine und veröffentlichen keine Binärpakete.

## Bekannte Grenzen

- Native 22.050-Hz-Synthese hat gegenüber Classic 11.025 Hz keinen nachgewiesenen qualitativen Gesamtvorteil. Die ursprüngliche Ausgabe bleibt empfohlen.
- Die gemeldete leise Hintergrundstörung bei Resampling und schneller Navigation ist nicht abschließend als behoben nachgewiesen.
- Japanisch besitzt bekannte native Fehler bei bestimmten Steuerzeichen; der Treiber filtert dort rohe Text-Tags. Polnisch ist noch unvollständig. Beide bleiben experimentell.
- Die Legacy-Zeichenkodierungen unterstützen nicht sämtliche Unicode-Zeichen. NVDAs Symbolverarbeitung und die passende Sprachwahl bleiben wichtig.
- Ein echter Windows-Anmeldevorgang wurde nicht getestet. Geprüft wurden ein isoliertes NVDA im sicheren Modus und die Konfigurationskopie mit Testziel.
- Die zusätzliche Verwaltungsoberfläche ist überwiegend deutsch; eine vollständige Übersetzung ist noch offen.

## Herkunft und Beiträge

Ausgangspunkt ist OpenEVV-Commit `0f2c8fad08c4fbfd1364b14993e3ccdcfcf9e6b6`, ergänzt um die lokal entwickelten NVDA-Änderungen bis zum Unicode-Testbuild vom 19. September 2026. Dieses Repository beginnt bewusst mit einer eigenen Versionsgeschichte des Treibers und übernimmt keine Engine-/SDK-Historie.

Fehlerberichte bitte mit NVDA-Version, Windows-/Engine-Version, Sprache, Stimme, Sample-Rate und einem möglichst kurzen Beispieltext. Keine privaten NVDA-Konfigurationen, Sprachdaten oder kommerziellen DLLs hochladen. Siehe [CONTRIBUTING.md](CONTRIBUTING.md).
