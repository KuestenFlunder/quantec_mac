# QUANTEC PRO -- Funktionale Spezifikation

**Datum**: 2026-04-05
**Methode**: Reverse Engineering (String-Analyse .exe, Hilfetexte, Settings, Logdateien, Datenbank-Inhalte)
**Ziel**: Vollstaendiges Verstaendnis der Software-Funktionalitaet fuer Mac-Portierung

---

## 1. Was ist QUANTEC PRO?

QUANTEC PRO ist eine **Radionics/Informationsfeld-Software** der QUANTEC GmbH. Sie steuert ein physisches USB-Hardwaregeraet (die "Diode") und verwaltet Klienten, deren Behandlungsziele ("Targets") und Behandlungsblaetter ("HealingSheets"). Der zentrale Vorgang heisst **"Bewellung"** -- die informatorische Uebertragung von Informationen aus einer esoterischen Wissensdatenbank ueber die Diode an ein Zielobjekt.

**Lizenz**: An die physische Diode gebunden. Ohne angeschlossene, lizenzierte Diode startet die Software nicht.

**Sprachen**: Deutsch, Englisch, Spanisch, Portugiesisch, Polnisch, Chinesisch, Koreanisch.

**Varianten**:
- **Standalone** -- Einzelplatz mit lokaler Diode (diese Installation)
- **Network/Central** -- Vernetzt mit QUANTEC-Zentrale ueber VPN (Port 48889)

---

## 2. Kern-Workflow

```
1. Client anlegen          → Kontaktdaten (Name, Adresse, Telefon, E-Mail)
2. Target erstellen        → Zielobjekt (Person, Tier, Ort), Foto, Geschlecht
3. HealingSheet erstellen  → Behandlungsblatt aus Scan-Ergebnissen oder manuell
4. Morphische Felder scannen → Diode identifiziert relevante Eintraege per Zufallsgenerator
5. Ergebnisse uebernehmen  → Items ins HealingSheet (mit Potenzen, QRS, Medien)
6. Affirmation formulieren → Positiver Zieltext, gemeinsam mit Klient
7. Sendeplan erstellen     → Intervall, Zeitraum, Modus festlegen
8. Bewellung starten       → Diode sendet Informationen an das Target
9. Butler ueberwacht       → Automatische Verlaengerung, Ersetzung nicht passender Items
10. Berichte drucken       → Dokumentation fuer Klient und Therapeut
```

---

## 3. Datenhierarchie

```
Client (Kontaktperson/Auftraggeber)
│   Name, Anrede, Titel, Adresse, Telefon, E-Mail,
│   Geburtstag, Versicherung, Geschlecht, Foto, Notizen
│
└── Target (Zielobjekt der Behandlung) [1:n pro Client]
    │   Name, Typ (Person/Tier/Ort), Geschlecht, Foto 1 + 2,
    │   Aktiv/Inaktiv, Notizen, Wiedervorlage
    │
    └── HealingSheet (Behandlungsblatt) [1:n pro Target]
        │   Name, Erstelldatum, Ablaufdatum, SendType,
        │   Sortierung, Aktiv/Inaktiv, IsTemplate,
        │   UseHsPicture, UseTargetPicture, HasAdvice
        │
        ├── HealingSheet-Item (Eintrag) [1:n pro Sheet]
        │       Text, Kommentar, Bild/Medien,
        │       PotencyKind (C/D/LM), PotencyValue, PotencyIntensity,
        │       QRS-Faktor, Farbe, SuppressPrinting, IgnoreOnCheck
        │
        ├── Affirmation (Positiver Zieltext)
        │
        └── Schedule (Sendeplan) [1:n pro Sheet]
                Typ (Direct/Interval/Random/Single/SMS),
                Start, Ende, Intervall, Dauer
                └── SendJob (konkreter Sendeauftrag) [1:n pro Schedule]
```

---

## 4. HealingSheet -- Detailformat

### 4.1 Felder eines HealingSheets

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| Name | Text | Frei waehlbarer Name des Behandlungsblatts |
| Erstelldatum | Datum | Automatisch gesetzt |
| Ablaufdatum | Datum | Optional, fuer zeitlich begrenzte Behandlungen |
| Aktiv | Boolean | Aktive Sheets werden schwarz, inaktive blau angezeigt |
| IsTemplate | Boolean | Kennzeichnet wiederverwendbare Vorlagen |
| SendType | Enum | Bewellungsmodus (Classic / ClassicWithMedia / Animated / AnimatedWithMedia) |
| SortOrder | Enum | ByDate, ByName, Automatic, Manual |
| UseHsPicture | Boolean | Sheet-eigenes Bild in die Transmission einbeziehen |
| UseTargetPicture | Boolean | Zielbild 1 des Targets mitschicken |
| HasAdvice | Boolean | Ob eine Affirmation/Empfehlung hinterlegt ist |
| MediaData | Binaer | Zugeordnete Mediendateien (Bilder, Audio, Video) |

### 4.2 Felder eines HealingSheet-Items

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| Text | Text | Haupttext (Mittelname, Affirmation, Information) |
| Comment | Text | Optionaler Kommentar zum Eintrag |
| PotencyKind | Enum | **C** (Centesimal 1:100), **D** (Dezimal 1:10), **LM** (Q-Potenzen 1:50.000) |
| PotencyValue | Integer | Potenz-Stufe (z.B. 30 fuer C30, 12 fuer D12) |
| PotencyIntensity | Float | Feinere Intensitaets-Abstufung |
| QrsFactor | Float | Quantenresonanz-Skalierungsfaktor pro Eintrag |
| Color | Enum | Farbmarkierung: Red, Blue, Green, Yellow, None |
| MediaData | Binaer | Dem Eintrag zugeordnetes Bild oder Medium |
| SuppressPrinting | Boolean | Eintrag beim Drucken unterdruecken |
| IgnoreOnCheck | Boolean | Bei Pruefungen ignorieren |
| DoNotExtend | Boolean | Bei Verlaengerung nicht ersetzen |
| MistakeCount | Integer | Wie oft als "nicht mehr passend" erkannt |
| RecentlyChangedByButler | Boolean | Kuerzlich automatisch geaendert |

### 4.3 Potenz-System (Homoeopathisch)

Das Potenz-System bildet die homoeopathische Verduennung/Verschuettelung ab:

| Art | Verduennung | Beispiele | Anwendung |
|-----|-------------|-----------|-----------|
| **D** (Dezimal) | 1:10 pro Stufe | D6, D12, D30 | Niedrige bis mittlere Potenzen |
| **C** (Centesimal) | 1:100 pro Stufe | C30, C200, C1000 | Mittlere bis hohe Potenzen |
| **LM** (Q-Potenzen) | 1:50.000 pro Stufe | LM6, LM12, LM30 | Sanfte Langzeitwirkung |

**PotencyValue**: Die Stufe (z.B. "30" bei C30).
**PotencyIntensity**: Zusaetzliche Feinabstimmung -- die Software kann Potenzen und Intensitaeten per Scan auf ein "Optimum" berechnen lassen.

### 4.4 QRS-Faktor

Der QRS-Faktor (Quanten-Resonanz-Skalierung) ist ein **numerischer Gewichtungswert pro HealingSheet-Eintrag**. Er wird:
- Im UI als Spalte "Pot/Int/QRS" zusammen mit Potenz und Intensitaet angezeigt
- Kann per Scan automatisch bestimmt werden
- Beeinflusst vermutlich die Sendedauer oder -intensitaet pro Item
- Anzeige ein-/ausschaltbar (Setting: `showQRS="True"`)

### 4.5 Affirmation (Advice)

Jedes HealingSheet kann eine **Affirmation** enthalten -- ein positiv formulierter Zieltext. Die Software prueft die Qualitaet der Formulierung und fordert den Benutzer auf:

> "Die Affirmation ist noch nicht optimal formuliert. Bitte pruefen Sie und beziehen Sie nach Moeglichkeit das Zielobjekt oder den Klient in die Formulierung ein."

Beispiel: "Rolf ist mutig und von tiefer innerer Ruhe erfasst."

### 4.6 HealingSheet-Lebenszyklus

1. **Erstellen**: Manuell, aus Vorlage, oder per ExpertScan
2. **Befuellen**: Items manuell eingeben ODER per Scanner aus morphischen Feldern einfuegen
3. **Potenzen/Intensitaeten optimieren**: Per Scan-Algorithmus ueber die Diode
4. **Senden**: Direkt an Diode oder ueber Sendeplan
5. **Verlaengern (Extend)**: Bei Ablauf werden nicht mehr passende Eintraege automatisch durch andere aus demselben morphischen Feld ersetzt
6. **Splitten**: Aufteilen in Koerper / Psyche / Geist / Seele
7. **Wiederherstellen**: Geloeschte Sheets aus Papierkorb restaurierbar

---

## 5. Bewellung -- Der Signal-Transmissions-Vorgang

### 5.1 Das Hardware-Geraet: Die Diode

| Eigenschaft | Details |
|-------------|---------|
| Name | QUANTEC Diode |
| Varianten | **QUANTEC6** (Standard), **QUANTEC6WithRandom** (mit Quantenrauschgenerator) |
| Anschluss | USB via FTDI-Chip (Treiber: CDM21226) |
| Protokoll | Seriell (RTS-Signal aktiv, UART optional) |
| Lizenz | An die physische Diode gebunden -- Software startet nicht ohne |
| Steckplaetze | Mindestens 3 konfigurierbar (type.0, type.1, type.2) |

Die Diode enthalt einen **Weissrausch-/Quantenrauschgenerator** (Variante "WithRandom"). Dieser erzeugt echte Zufallsdaten, die fuer den Scan-Algorithmus verwendet werden. Die Zufallsdaten werden interpretiert als "Antwort des Informationsfeldes" auf die Frage, welche Eintraege fuer das Zielobjekt relevant sind.

### 5.2 Was passiert bei einer Bewellung?

Die "Bewellung" (engl. "Radiation"/"Transmission") ist der Kern-Vorgang:

```
HealingSheet
    ├── Item 1: "Acidum nitricum C30" + QRS 0.8
    ├── Item 2: "Angst loslassen" (Affirmation)
    ├── Item 3: [Bild des Targets]
    └── Item 4: [Medien-Datei]
        │
        ▼
    Diode (USB)
        │
        ▼
    "Informationsfeld" → Zielobjekt (Target)
```

Die Software sendet die **Informationen des HealingSheets** (Texte, Potenzen, Bilder, Medien) ueber die USB-Diode. Der Sendevorgang umfasst:

1. **Textuelle Information**: Die Eintraege des HealingSheets
2. **Potenz-/Intensitaets-Modulation**: Beeinflusst vermutlich die Art der Sendung
3. **Bilder**: Target-Foto und/oder HealingSheet-Bild werden "mitgesendet"
4. **Medien**: Audio/Video-Dateien bei AnimatedWithMedia-Modus
5. **Dauer**: Jede Sendung hat eine definierte Dauer (Standard: 12 Sekunden)

### 5.3 Sende-Modi

| Modus | Beschreibung |
|-------|-------------|
| **Classic** | Nur Text/Information wird uebertragen |
| **ClassicWithMedia** | Text + zugeordnete Medien (Bilder) |
| **Animated** | Animierter Modus (erfordert spezielle Lizenz + ExtensiveStorage) |
| **AnimatedWithMedia** | Animiert + Medien (**aktuell konfiguriert** bei dieser Installation) |

### 5.4 Sendeplan (Schedule)

| Typ | Beschreibung |
|-----|-------------|
| **Direct** | Sofort-Sendung, einmalig |
| **Single** | Geplante Einzelsendung zu bestimmtem Zeitpunkt |
| **Interval** | Wiederkehrend in festem Intervall (Standard: alle 3 Stunden) |
| **Random** | Zu zufaelligen Zeitpunkten innerhalb eines Zeitfensters |
| **SMS** | Ausgeloest durch SMS des Klienten (ueber App/SMS-Trigger) |

**Konfigurierte Standardwerte** (aus .settings):
- AutoStart: 5 Minuten nach Programmstart
- Standardintervall: 3 Stunden
- Standarddauer: 12 Sekunden pro Sendung
- Ablaufzeitraum: 12 Monate

### 5.5 Butler (Automatischer Hintergrund-Service)

Der **Butler** ist ein automatisierter Assistent der:
- Aktive Sendepläne ueberwacht
- Bei Ablauf eines HealingSheets automatisch verlaengert
- Nicht mehr passende Eintraege durch neue aus demselben morphischen Feld ersetzt
- Items als "RecentlyChangedByButler" markiert
- Empfehlungen fuer Sendeplan-Anpassungen gibt

### 5.6 Offline- und App-Bewellung

- **Offline**: Sendungen koennen auch ohne Netzwerkverbindung ausgefuehrt werden
- **App-Bewellung**: Klienten koennen per Smartphone-App eine Bewellung anfordern
  - Verwendet ein **Triggerwort** zur Ausloesung
  - App-Berechtigung hat ein Ablaufdatum
  - SMS-Benachrichtigung bei Erfolg/Ablauf
- **SMS-Trigger**: Pro Client kann ein eindeutiger SMS-Trigger konfiguriert werden

---

## 6. Scanner-Funktionalitaet

### 6.1 Prinzip

Der Scanner nutzt den **Quantenrauschgenerator** der Diode um aus einer Auswahl morphischer Felder diejenigen Eintraege zu identifizieren, die fuer das aktuelle Zielobjekt "relevant" sind. Die Zufallsdaten des Rauschgenerators werden als "Antwort des Informationsfeldes" interpretiert.

### 6.2 Scan-Typen

| Scan | Beschreibung |
|------|-------------|
| **Standard-Scan** | Durchsucht ausgewaehlte morphische Felder in konfigurierbaren Zyklen |
| **QuickScan** | Schnellanalyse fuer ein Target (liefert ein Stichwort, z.B. "Kraft") |
| **ExpertScan** | Vorkonfigurierte umfangreiche Scan-Vorlagen, importierbar/exportierbar |
| **Scan Potenzen** | Bestimmt optimale homoeopathische Potenzen fuer bestehende Items |
| **Scan Intensitaeten** | Bestimmt optimale Intensitaetswerte |
| **Scan Potenzen + Intensitaeten** | Beides zusammen |
| **Scan Sendeplan** | Optimiert Intervall, Dauer und Zeitraum des Sendeplans |
| **Scan Zahnstatus** | Dental-Modul: Belastungen einzelner Zaehne |
| **Scan Reflexzonen** | Reflex-Modul: Belastungen der Fuss-Reflexzonen |
| **Scan Wirbelsaeule** | Spinal-Modul: Belastungen einzelner Wirbel |

### 6.3 Scan-Ablauf

1. Benutzer waehlt **morphische Felder** oder eine **Scan-Vorlage** aus
2. Scan-Parameter einstellen: Zyklen (Standard: 88), Max. Felder (21), Geschlecht beruecksichtigen
3. **Start** (Ctrl+S oder Button)
4. Diode erzeugt Zufallsdaten ueber den Rauschgenerator
5. Software interpretiert die Zufallsdaten als Auswahl aus den morphischen Feldern
6. **Ergebnisse** werden angezeigt: Feld, Pfad, Treffer, Prozent, Rang, QRS-Wert
7. Benutzer uebernimmt Ergebnisse (alle oder ausgewaehlte) ins HealingSheet
8. Optional: Vorherige Ergebnisse beibehalten (konfigurierbar)

### 6.4 Scan-Konfiguration (aus .settings)

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| cycles | 88 | Anzahl Durchlaeufe pro Scan |
| morphicFields | 21 | Max. Felder pro Scan |
| count | 21 | Max. Ergebnisse |
| useGender | True | Geschlecht des Targets beruecksichtigen |
| keepResults | True | Vorherige Ergebnisse nicht verwerfen |

---

## 7. Morphische Felder (Wissensdatenbank)

### 7.1 Struktur

Die morphischen Felder sind eine **hierarchische Baum-Datenbank** mit 117.030 Eintraegen in 256 Kategorien, organisiert in 24 Themengebieten. Sie bilden die Informationsbasis fuer Scans und HealingSheet-Eintraege.

### 7.2 Bedienung

- **Erstellen**: Neue Felder/Zweige/Eintraege anlegen
- **Suchen**: Volltextsuche, auch in Kommentaren, mit Suchvorlagen
- **Kategorisieren**: Felder in Kategorien organisieren
- **Import/Export**: Eigenes Format + XML-Format
- **PDF-Import**: Eintraege aus PDF-Dokumenten importieren
- **Drucken**: Inkl. Kommentare

### 7.3 Generator

Der Generator assistiert beim Einfuegen von Eintraegen aus morphischen Feldern in ein HealingSheet. Er arbeitet mit dem Scan-Algorithmus und praesentiert "Generator-Ergebnisse" die der Benutzer uebernehmen kann.

### 7.4 Themengebiete der Wissensdatenbank

| # | Themengebiet | Items | Inhalt |
|---|-------------|-------|--------|
| 1 | Nosoden & Infektiologie | ~23.000 | Krankheitserreger-Nosoden, Viren, Parasiten, Allergene |
| 2 | Affirmationen & Weisheiten | ~16.000 | Heilaffirmationen, Lebensweisheiten, Tugenden, Sprichwoerter |
| 3 | Homoeopathie & Praeparate | ~15.000 | Materia Medica, Arzneimittel, Komplexmittel (Heel), Spagyrik |
| 4 | Religion & Spiritualitaet | ~14.000 | Koran (komplett deutsch), Bibel, Engel, Kabbala, Mantras |
| 5 | Medizin & Genetik | ~9.000 | ICD-10 Codes, Chromosomen/OMIM, Biochemie |
| 6 | Edelsteine & Kristalle | ~5.000 | Heilsteine, Meditationen, Lexikon, Wirkungen |
| 7 | Phytotherapie & Pflanzen | ~4.000 | Kraeuter, Heilpflanzen, Gemmotherapie, Baumheilkunde |
| 8 | Enzymklassifikation | ~3.800 | EC-Nummern (Oxidoreduktasen, Transferasen, etc.) |
| 9 | TCM & Akupunktur | ~3.400 | 361 Akupunkturpunkte, Meridiane, 5-Elemente, Feng Shui |
| 10 | Tarot & Archetypen | ~3.100 | Grosse/Kleine Arkana, Archetypen, Deutungen |
| 11 | Anatomie & Physiologie | ~2.500 | Organsysteme, Hirnnerven, Wirbelsaeule, Zellbiologie |
| 12 | Geobiologie & Geopathie | ~2.300 | Erdstrahlen, Gitter-Systeme, Raum-Energetisierung |
| 13 | Nahrungsergaenzung & Pharma | ~2.100 | Vitamine, Aminosaeuren, Schuessler-Salze |
| 14 | Symbole & Kraftplaetze | ~1.700 | Krafttiere, Kornkreise, Wallfahrtsorte, Heilige Geometrie |
| 15 | Astrologie & Numerologie | ~1.400 | Maya-Kalender, Haeuser, Zahlenlehre |
| 16 | Spirituelle Kurse | ~1.300 | ACIM (A Course in Miracles) Lektionen |
| 17 | Psychologie & Therapie | ~1.300 | Psychosomatik, Familienaufstellung, Radionik |
| 18 | Chakren & Energiearbeit | ~1.100 | Chakren, Aura-Therapie, Jin Shin Jyutsu |
| 19 | Alternative Heilverfahren | ~1.000 | Anthroposophie, CERES, Heilerde |
| 20 | Klang & Frequenzen | ~900 | Planetenfrequenzen, Organtoene, Klangtherapie |
| 21 | Aromatherapie | ~750 | Aetherische Oele, Anwendungen, Wirkungen |
| 22 | Bluetentherapie | ~500 | Bach-Blueten, Kalifornische Essenzen, Maya-Heilpflanzen |
| 23 | Tierheilkunde | ~1.400 | Veterinaer-Homoeopathie, Tierkrankheiten-Nosoden |
| 24 | Sonstige | ~2.400 | BWL/Business-Optimierung, Radionik, Mandalas |

---

## 8. Spezial-Module

### 8.1 Zahnmodul (Module.Dental)

- Zeigt grafischen **Zahnstatus** an
- Per Scan werden **Belastungen einzelner Zaehne** ermittelt
- Belastungsstufen: leicht, mittel, stark
- Zaehne koennen Eintraegen zugeordnet werden
- Eigener Bericht (Report.DentalStatus)

### 8.2 Reflexzonen-Modul (Module.Reflex)

- Zeigt **Fuss-Reflexzonen** in 8 Ansichten:
  - Linke/Rechte Fusssohle
  - Linke/Rechte Aussenseite
  - Linke/Rechte Innenseite
  - Linke/Rechte Rueckseite
- Per Scan werden Belastungen der Zonen ermittelt
- Belastungsstufen: leicht, mittel, stark
- Eigener Bericht (Report.ReflexZoneStatus)

### 8.3 Wirbelsaeulen-Modul (Module.Spinal)

- Zeigt grafischen **Wirbelsaeulenstatus** an
- Per Scan werden Belastungen einzelner Wirbel ermittelt
- Belastungsstufen: leicht, mittel, stark
- Uebersicht: Wirbel → zugeordnete Erkrankungen
- Eigener Bericht (Report.SpinalStatus)

### 8.4 Psychosomatik-Modul

- ExpertScan-Erweiterung fuer psychosomatische Zusammenhaenge
- Version: "Psychosomatik 7.0"
- Eigene Scan-Vorlagen

---

## 9. Berichte

| Bericht | Inhalt |
|---------|--------|
| Client-Stammblatt | Kontaktdaten des Klienten |
| Target-Datenblatt | Zielobjekt-Informationen |
| HealingSheet-Bericht | Vollstaendiges Behandlungsblatt mit allen Items |
| HealingSheet-Uebersicht | Kompakte Auflistung aller Sheets |
| Sendejob-Bericht | Transmissionsdaten der letzten 30 Tage |
| SMS-Sendebericht | SMS-basierte Sendungen |
| Scan-Ergebnisse | Letzte Scanner-Resultate |
| Morphische Felder | Ausdrucke der Wissensdatenbank |
| Zahnstatus | Grafischer Zahnbefund |
| Reflexzonenstatus | Grafischer Fussbefund |
| Wirbelsaeulenstatus | Grafischer Wirbelbefund |
| Adressliste | Alle Klienten mit Adressen |
| Geburtstagsliste | Anstehende Geburtstage |
| Notizen | Gesammelte Notizen |
| Datenbank-Statistik | Speicherverbrauch, Anzahl Records |
| Belastungsbericht | Zusammenfassung aller Stresses |
| Ablaufende Sheets | HealingSheets die bald ablaufen |
| Kategorie-Bericht | Morphische-Feld-Kategorien |

---

## 10. Netzwerk und Fernzugriff

### 10.1 Standalone vs. Network

| Modus | Beschreibung |
|-------|-------------|
| **Standalone** | Einzelplatz, lokale Diode, lokale Datenbank |
| **Network** | Mehrere Workstations, zentraler Server mit Diode |

### 10.2 QUANTEC Zentrale

- Verbindung zu zentraler Infrastruktur (188.40.196.214:48889)
- Heartbeat-Monitoring alle 30 Sekunden
- App & VPN-Dienst
- Server-Registrierung erforderlich

### 10.3 Mobile App

- Klienten koennen per App eine Bewellung bei ihrem Therapeuten anfordern
- **Triggerwort** zur Ausloesung (pro Client konfigurierbar)
- Ablaufdatum fuer App-Berechtigung
- Benachrichtigungen: "Bewellung wurde veranlasst", "Berechtigung laeuft in 3 Tagen ab"

---

## 11. Import / Export

| Format | Import | Export | Beschreibung |
|--------|:------:|:------:|-------------|
| Morphische Felder (eigenes) | Ja | Ja | Proprietaeres .mf-Format |
| Morphische Felder (XML) | Ja | -- | XML-Format |
| ExpertScans (eigenes) | Ja | Ja | Proprietaeres .es-Format |
| Medien | Ja | Ja | Bilder, Audio, Video |
| Datenbank (komplett) | Ja | Ja | Proprietaeres .store/.dbaf-Format |
| PDF | Ja | -- | PDF-Dokumente in morphische Felder importieren |
| PLZ/Ort | Ja | -- | Postleitzahlen-Datenbank |
| QUANTEC 6 (Legacy) | Ja | -- | Migration vom Vorgaengerprodukt (.quantec.expert) |

---

## 12. Benutzerverwaltung

- Aktivierbar/Deaktivierbar (aktuell: deaktiviert)
- Login/Logout mit Passwort
- **Masterpasswort** fuer Administratorfunktionen
- Passwort per SMS anforderbar
- Zugriffsrechte: Voller Zugriff oder eingeschraenkt
- Benutzer erstellen, aendern, loeschen

---

## 13. UI-Aufbau

### 13.1 Hauptbereiche (Topics/Controls)

| Bereich | Beschreibung |
|---------|-------------|
| **Klientenverwaltung** | Client anlegen, bearbeiten, suchen |
| **Zielobjekte** | Targets pro Client verwalten |
| **HealingSheet-Editor** | Sheets erstellen, Items bearbeiten |
| **Sendeplaner/Kalender** | Schedule erstellen, Kalenderansicht |
| **Morphische Felder** | Wissensdatenbank durchsuchen/bearbeiten |
| **Zahnmodul** | Zahnstatus-Ansicht mit Scan |
| **Reflexzonenmodul** | Fusszonen-Ansicht mit Scan |
| **Wirbelsaeulenmodul** | Wirbelsaeulen-Ansicht mit Scan |
| **ExpertScan** | Erweiterte Scan-Verwaltung |
| **Berichte** | Berichts-Auswahl und Druck |
| **Einstellungen** | Konfiguration aller Parameter |
| **Datenbank** | Backup, Import/Export, Optimierung |
| **Konto** | Benutzerverwaltung |
| **Zentrale** | Verbindung zum QUANTEC-Server |

### 13.2 UI-Features

- **Split-Screen**: Fenster teilen fuer paralleles Arbeiten
- **Drag & Drop**: Fuer Clients und HealingSheets
- **Baumansicht**: Hierarchische Navigation Client → Target → Sheet
- **Kalenderansicht**: Tagesansicht fuer Sendepläne
- **Geburtstags-Popup**: Erinnerung bei Programmstart
- **Termin-Erinnerungen**: 5 Min bis 1 Tag vorher
- **Dioden-Logo**: Statusanzeige im Footer (verbunden/getrennt)
- **Dark/Light Theme**: Umschaltbar
- **Bildschirm-Skalierung**: Anpassbar
- **Rechtschreibpruefung**: Fuer HealingSheet-Texte

---

## 14. Konfiguration (aktuelle Werte)

| Einstellung | Wert | Beschreibung |
|-------------|------|-------------|
| Bewellungsmodus | AnimatedWithMedia | Animiert mit Medien |
| Auto-Start | 5 Minuten | Bewellung startet 5 Min nach Programmstart |
| Standard-Intervall | 3 Stunden | Zwischen zwei Sendungen |
| Standard-Dauer | 12 Sekunden | Pro Sendung |
| Ablaufzeitraum | 12 Monate | HealingSheets laufen nach 12 Monaten ab |
| Scan-Zyklen | 88 | Durchlaeufe pro Scan |
| Scan-Felder | 21 | Max. morphische Felder pro Scan |
| Geschlecht beruecksichtigen | Ja | Beim Scannen |
| QRS anzeigen | Ja | Im HealingSheet |
| Rechtschreibpruefung | Ja | Aktiv |
| Sortierung HealingSheets | Nach Name | |
| Sortierung Morphische Felder | Automatisch | |
| Dioden-Typ | QUANTEC6 | Alle 3 Steckplaetze |
| Auto-Update | Aktiv | Prueft servicecenter.quantec.eu per FTP |
| Benutzerverwaltung | Deaktiviert | |
| Backup-Verzeichnis | C:\Users\Ben\Desktop\Quantec Sicherung | |

---

## 15. Besondere Anwendungsbereiche

### 15.1 Tier-Behandlung

Die Software hat ein vollstaendiges Veterinaer-Modul:
- Target-Typ "Tier" mit eigenen morphischen Feldern (751 Vet-Nosoden, 355 Vet-Homoeopathie, 579 Tierkrankheiten-Nosoden)
- Bestaetigte Nutzung aus Target-Notes: "Fifi geht es sehr gut. Besten Dank."

### 15.2 Raum-/Ort-Behandlung

QUANTEC kann auch **Raeume und Orte** "bewellen":
- Eigene Kategorie "Raum-Energetisierung" (348 Items)
- Geobiologie/Erdstrahlen-Analyse
- Target kann ein Ort/Gebaeude sein
- PLZ-Datenbank fuer Standort-Zuordnung

### 15.3 Business-Optimierung

Ueberraschenderweise enthaelt die Wissensdatenbank auch BWL-Inhalte:
- BWL/Controlling (141 Items): Profit-Center, Leistungskennzahlen
- BWL/Marketing (143 Items): Kommunikationspolitik, Marktforschung
- QUANTEC wird auch fuer **geschaeftliche Optimierung** eingesetzt

### 15.4 Rechtliche Dokumente

Eine Kategorie "Rechtliche Dokumente/Vertraege" (213 Items) mit juristischen Texten wie "Aktueller beglaubigter Handelsregisterauszug" -- vermutlich fuer die geschaeftliche Anwendung.

---

## 16. Zusammenfassung: Kern-Erkenntnisse fuer die Mac-Portierung

### Was muss die Mac-App koennen:

1. **Klienten-/Target-/HealingSheet-Verwaltung** mit der beschriebenen 3-Ebenen-Hierarchie
2. **HealingSheet-Editor** mit Items, Potenzen (C/D/LM), Intensitaet, QRS, Farben, Medien
3. **Scanner** der ueber die USB-Diode morphische Felder analysiert (Zufallsgenerator-basiert)
4. **Bewellungs-Engine** die HealingSheets ueber die Diode sendet (4 Modi, 5 Zeitplan-Typen)
5. **Butler** als automatischer Hintergrund-Service
6. **Morphische-Feld-Browser** mit Volltextsuche und hierarchischer Navigation
7. **3 Spezialmodule** (Zahn, Reflexzonen, Wirbelsaeule) mit grafischer Darstellung
8. **Berichtswesen** (18+ Berichtstypen)
9. **USB-Kommunikation** mit der FTDI-Diode (serielles Protokoll, RTS-Signal)

### Was die Diode tatsaechlich tut:

Die Diode ist ein USB-Geraet mit FTDI-Chip das:
- **Beim Scannen**: Quantenrausch-Zufallsdaten liefert, die die Software als Auswahl aus der Wissensdatenbank interpretiert
- **Beim Senden**: Informationen aus dem HealingSheet empfaengt und "ins Informationsfeld uebertraegt"
- **Kommunikation**: Serielles Protokoll (FTDI CDM21226), RTS-Signal aktiv, UART optional
- **Lizenz**: Geraete-gebundene Lizenz, ohne Diode keine Funktion

Das genaue Protokoll (welche Bytes ueber die serielle Schnittstelle gesendet werden) ist noch nicht entschluesselt -- dafuer waere ein USB-Sniffer auf einem funktionierenden Windows-System noetig.
