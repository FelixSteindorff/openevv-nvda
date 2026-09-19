# Testen

## Ohne Engine

```powershell
python nvda/test/sequence.py
python nvda/test/engine.py
python nvda/test/settings.py
python tools/check_repository.py
```

Die Engine-Tests injizieren gezielt Fehler, unter anderem ungültige Sample-Raten und einen blockierten Player. Entsprechende Logmeldungen sind erwartet; entscheidend sind Exitcode und die abschließende Erfolgsmeldung. Es wird keine installierte NVDA-Instanz verändert.

## Mit separat bereitgestellter OpenEVV-x64-DLL

Die folgenden Tests wurden mit der lokalen, mehrsprachigen Entwicklungs-DLL durchgeführt. Die DLL ist hier nicht enthalten. Mehrsprachige Tests erwarten deren zehn Sprachvarianten; fehlende Sprachen sind eine andere Testkonfiguration, keine automatische Treiberregression.

```powershell
python nvda/test/settings.py --dll C:/mein-lokaler-pfad/eci.dll --out build/settings
python nvda/test/features.py --dll C:/mein-lokaler-pfad/eci.dll --out build/features
python nvda/build.py --version 0.1.0 --dll C:/mein-lokaler-pfad/eci.dll
python -m zipfile -e build/openevv-0.1.0.nvda-addon build/packaged
python nvda/test/windows.py build/packaged
python nvda/test/unicode_hyphens.py --addon build/packaged --out build/hyphens
python nvda/test/unicode_text.py --addon build/packaged --out build/unicode
```

Alle Ausgaben unter `build/` sind lokal und von Git ausgeschlossen. Sie können IBM-Daten, Audio oder lokal konfigurierte Werte enthalten und gehören nicht automatisch in öffentliche Issues oder Releases.

Die Unicode-Tests vergleichen je Sprache und Schreibweise getrennte Prozesse, damit globaler Legacy-Engine-Zustand nicht zwischen Referenz und Vergleich überlebt. Sie prüfen PCM-Gleichheit mit einer definierten Referenz, nicht die muttersprachliche Qualität beliebiger Texte.

## Dokumentierter Ausgangsstand

Die lokale Variante vor dieser Repository-Abtrennung bestand Tests mit echter DLL für Sprache/Stimme/Persistenz, DE/EN mit acht Stimmen, schnelle temporäre Sprachwechsel, Stop/Folgeausgabe und sieben Sample-Raten. Die Aussprachewerkzeuge bestanden 56 Vorschauen; 251 WPM-Rohwerte wurden mit der Engine verglichen. Die Unicode-Erweiterung bestand 170 Layout-/Typografiefälle und 18 PCM-Paarvergleiche sowie normale deutsche und englische Sprachausgabe in echtem NVDA 2026.2 auf einem isolierten Desktop.

Diese Ergebnisse betreffen eine konkrete lokale DLL. Die öffentliche CI prüft die separat ausführbaren Python-Tests; sie behauptet keine erneute Validierung einer nicht enthaltenen Engine. Interaktive NVDA-Tests, ein Hörtest und ein echter Windows-Anmeldevorgang bleiben gesonderte Prüfungen.
