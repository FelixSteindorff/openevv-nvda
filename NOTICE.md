# Herkunft und Lizenzumfang

Die hier enthaltenen Treiber-, Build- und Testquellen basieren auf dem NVDA-Verzeichnis von [Mudb0y/openevv](https://github.com/Mudb0y/openevv), Copyright 2026 Stanislaw Przedzinkowski, MIT-Lizenz. Die weiterentwickelte Variante wird von Felix Steindorff gepflegt. Die ursprünglichen Copyright- und Lizenzhinweise bleiben in `LICENSE` erhalten.

Dieses Repository enthält **keine OpenEVV-Engine-DLL, keine rekonstruierten nativen Engine-Quellen, keine IBM-Sprachmodule, keine Synthesetabellen und kein IBM-SDK**. Die MIT-Lizenz dieses Repositorys vergibt dafür keine Rechte.

Das ursprüngliche OpenEVV-Projekt unterscheidet seine eigenen Arbeiten von den aus IBM Embedded ViaVoice übernommenen Sprachdaten und Tabellen: [Upstream NOTICE](https://github.com/Mudb0y/openevv/blob/main/NOTICE). Insbesondere werden IBM-Sprachdaten nicht dadurch MIT-lizenziert, dass sie in einem GitHub-Repository stehen oder in einer neu kompilierten DLL enthalten sind.

Bei der Prüfung des originalen Embedded ViaVoice 4.3 SDK (Oktober 2004, AT2T5ZZ) wurde eine Weitergabeerlaubnis für Beispielprogramme gefunden, aber keine allgemeine Freigabe zur Bearbeitung und öffentlichen Weitergabe der Sprachdaten und daraus erstellter Laufzeitbibliotheken. Die SDK-Dokumentation verweist für das Produkt auf separate IBM-Verträge. Eine vollständige produktspezifische Lizenzvereinbarung wurde nicht ermittelt. Das ist eine Beschreibung der Recherche, keine verbindliche Rechtsberatung oder abschließende Bewertung sämtlicher möglicher Nutzungsrechte.

Ein lokaler Build mit `--dll` nimmt die vom Benutzer bereitgestellte Bibliothek in das Add-on auf. Der Benutzer muss die für Beschaffung, Nutzung und gegebenenfalls Weitergabe erforderlichen Rechte selbst klären. Eine erfolgreiche technische Prüfung oder ein Lizenzhinweis ersetzt diese Rechte nicht. CI lädt und verteilt keine Engine.

Die optionalen Zusatzwörterbücher stammen aus [AltIBMTTSDictionaries](https://github.com/mohamed00/AltIBMTTSDictionaries) und [IBMTTSDictionaries](https://github.com/eigencrow/IBMTTSDictionaries). Sie werden nur auf Anforderung separat heruntergeladen, gehören nicht zum Repository und behalten ihre jeweiligen Lizenzbedingungen. Ihre Dateien werden nicht durch die MIT-Lizenz des Treibers neu lizenziert.

OpenEVV, IBM, ViaVoice, Eloquence und NVDA bezeichnen die jeweiligen Projekte beziehungsweise Produkte. Dieses Repository ist eine unabhängige Weiterentwicklung und beansprucht keine offizielle Unterstützung durch deren Anbieter.
