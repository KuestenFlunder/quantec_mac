# QUANTEC PRO -- Hardware Reverse Engineering

**Datum**: 2026-04-05
**Methode**: de4dot Deobfuskierung von SmartAssembly 6.9.0.114, Metadata-Analyse der extrahierten Hardware.dll
**Quellcode-Pfad** (original): `C:\QUANTEC\QV7\Hardware\`

---

## 1. Deobfuskierung

SmartAssembly 6.9.0.114 wurde mit **de4dot** (.NET Core Fork) erfolgreich entfernt. Aus der monolithischen `QUANTEC PRO.exe` (6.2 MB) wurden **9 eingebettete Assemblies** extrahiert:

| Assembly | Groesse | Funktion |
|----------|---------|----------|
| **Hardware.dll** | 714 KB | FTDI-Dioden-Kommunikation (Kernfund) |
| Core.dll | 349 KB | Entity-Modell, Module, Reports |
| Foundation.dll | 146 KB | FTP, Excel-Export, Logging |
| Storage.dll | 114 KB | Datenbank-Persistenz (.store Format) |
| Migration.dll | 52 KB | DB-Migration von QUANTEC 6 |
| Scopes.dll | 30 KB | Scope/Kontext-Management |
| Network.dll | 28 KB | Server-Kommunikation |
| CoreServices.dll | 21 KB | Service-Interfaces |
| License.dll | 18 KB | Lizenz-Validierung |

Die deobfuskierten Dateien liegen unter: `claudedocs/deobfuscated/`

---

## 2. FTDI-Chip: Das Dioden-Bauteil

### 2.1 Unterstuetzte FTDI-Chips

Die Hardware.dll unterstuetzt folgende FTDI-Chipfamilien:

| Chip | Typ | Eigenschaften |
|------|-----|---------------|
| **FT232R** | USB-UART | Gaengigstes Modell, 1 Kanal, bis 3 Mbit/s |
| **FT232B** | USB-UART | Aelteres Modell, 1 Kanal |
| **FT232AM** | USB-UART | Erstes Modell der Serie |
| **FT232H** | Hi-Speed | USB 2.0 Hi-Speed, MPSSE, 1 Kanal |
| **FT2232H** | Hi-Speed Dual | 2 unabhaengige Kanaele, MPSSE |
| **FT4232H** | Hi-Speed Quad | 4 Kanaele |
| **FT223C** | USB-UART | Neueres Modell |
| **FTXSeries** | Neueste Serie | FT230X/FT231X/FT234X |
| **FT100AX** | Legacy | Aeltestes Modell |

### 2.2 Wahrscheinlichster Chip

Basierend auf der Konfiguration (`DiodeType: QUANTEC6`, 3 Steckplaetze in den Settings, BitBang-Modus) ist der wahrscheinlichste Chip:

**FT232R oder FT232B** -- Gruende:
- Standard-USB-UART-Chip, am weitesten verbreitet
- Unterstuetzt BitBang-Modus (AsyncBitBang, SyncBitBang, CBUSBitBang)
- 4 CBUS-Pins (Bit0-Bit3) fuer direkten Pin-Zugriff
- FTDI VID: 0x0403, Standard-PID: 0x6001
- Der FTDI-Treiber CDM21226 in den Update-Dateien ist fuer die FT232-Familie

### 2.3 USB-Identifikation

| Eigenschaft | Wert |
|-------------|------|
| USB Vendor ID | 0x0403 (FTDI) |
| USB Product ID | Vermutlich 0x6001 (FT232) oder custom |
| Treiber | CDM21226 (FTDI D2XX + VCP Combined Driver) |
| Identifikation | VIDPID-Feld + FTID_GetChipIDFromHandle (unique Chip-ID) |
| Lizenz | An die einzigartige Chip-ID gebunden |

---

## 3. Kommunikationsprotokoll

### 3.1 Treiber-Schicht

Die Software verwendet **NICHT** den virtuellen COM-Port (kein System.IO.Ports), sondern die **FTDI D2XX Direct API**:

```
Hardware.dll
    ↓ LoadLibrary("ftd2xx.dll") / LoadLibrary("FTD2XX.dll")
    ↓ GetProcAddress() fuer jede FT_xxx Funktion
    ↓
Native FTDI D2XX API (26 Funktionen)
```

Die DLL wird zur Laufzeit dynamisch geladen (`LoadLibrary`/`GetProcAddress`), nicht statisch gelinkt.

### 3.2 FTDI-API Funktionen (vollstaendig)

**Geraete-Management:**
| Funktion | Beschreibung |
|----------|-------------|
| `FT_CreateDeviceInfoList` | Zaehlt angeschlossene FTDI-Geraete |
| `FT_GetDeviceInfo` | Geraeteinformationen lesen |
| `FT_GetDeviceInfoDetail` | Detaillierte Geraeteinformationen |
| `FT_Open` / `FT_OpenEx` | Geraet oeffnen (nach Index oder Serial) |
| `FT_Close` | Geraet schliessen |
| `FT_ResetDevice` / `FT_ResetPort` | Geraet/Port zuruecksetzen |
| `FT_CyclePort` | USB-Port recyclen |
| `FTID_GetChipIDFromHandle` | Einzigartige Chip-ID lesen (Lizenz!) |

**Konfiguration:**
| Funktion | Beschreibung |
|----------|-------------|
| `FT_SetBaudRate` | Baudrate setzen |
| `FT_SetDataCharacteristics` | Wortlaenge (7/8 Bit), StopBits, Parity |
| `FT_SetFlowControl` | Flusskontrolle: RtsCts, DtrDsr, XonXoff, None |
| `FT_SetTimeouts` | Lese-/Schreib-Timeouts |
| `FT_SetBitMode` | **BitBang-Modus aktivieren** |

**Daten-IO:**
| Funktion | Beschreibung |
|----------|-------------|
| `FT_Read` | Bytes vom Geraet lesen |
| `FT_Write` | Bytes an das Geraet schreiben |
| `FT_GetStatus` | Bytes in RX/TX-Queue abfragen |
| `FT_Purge` | RX/TX-Buffer leeren |
| `FT_GetBitMode` | Aktuellen Pin-Zustand lesen |

**Signal-Steuerung:**
| Funktion | Beschreibung |
|----------|-------------|
| `FT_SetRts` / `FT_ClrRts` | RTS-Signal setzen/loeschen |
| `FT_SetDtr` / `FT_ClrDtr` | DTR-Signal setzen/loeschen |
| `FT_GetModemStatus` | CTS, DSR, DCD, RI Status lesen |

### 3.3 Betriebs-Modi

| Modus | Enum-Wert | Beschreibung |
|-------|-----------|-------------|
| **UART** | Standard | Normaler serieller Modus |
| **AsyncBitBang** | BitBang | Asynchroner Direktzugriff auf Pins |
| **SyncBitBang** | BitBang | Synchroner Direktzugriff auf Pins |
| **CBUSBitBang** | BitBang | CBUS-Pin Direktzugriff (Bit0-Bit3) |
| **SyncFIFO** | FIFO | Synchroner FIFO-Modus |
| **MPSSE** | Hi-Speed | Multi-Protocol Synchronous Serial Engine |

### 3.4 BitBang-Modus (der Kern)

Im BitBang-Modus werden die **8 Datenpins (D0-D7) des FTDI-Chips direkt als GPIO** angesprochen. Jeder Pin kann individuell als Ein- oder Ausgang konfiguriert werden. Die Pins Bit0-Bit3 (D0-D3) werden explizit im Code referenziert.

**Fuer den Scan**: Die Diode liest Zufallsbits von einem Rauschgenerator der an den Eingangspins haengt → `ReadBits`/`ReadBytes`/`ReadUInt8`

**Fuer das Senden**: Die Diode schreibt Daten an die Ausgangspins → `FT_Write` im BitBang-Modus

---

## 4. Dioden-Klassen-Hierarchie

```
BasicDiode
├── Verbindung: FT_Open → FT_SetBaudRate → FT_SetBitMode
├── Zustand: DiodeState (Idle/Scanning/Sending/NotOpened/NotFound)
├── Signalqualitaet: CheckSignalQuality, signalDropout
├── Lizenz: FTID_GetChipIDFromHandle → chipId
│
├── QUANTEC6Diode (Standard)
│   └── Standard-Betrieb ohne externen Zufallsgenerator
│
├── QUANTEC6DiodeWithRandom (erweitert)
│   └── Mit externem Quantenrausch-Zufallsgenerator
│
├── SelectionDiode
│   ├── Fuer den SCAN-Vorgang
│   ├── Liest Zufallsbits: ReadBits → bitBuffer
│   ├── Modi: FirstScan, InBetweenScan, LastScan, SingleScan
│   └── Cycles-Steuerung (konfigurierbar, Standard: 88)
│
├── DistributionDiode
│   ├── Fuer den SENDE-Vorgang ("Bewellung")
│   ├── Schreibt Daten: FT_Write
│   └── BaseAverage, Distribution-Algorithmus
│
└── RemainderDiode
    └── Verarbeitung von Rest-Daten/Bits
```

---

## 5. Der Rauschgenerator

### 5.1 Physisches Prinzip

Die QUANTEC-Diode enthaelt neben dem FTDI-Chip einen **Rauschgenerator** (bei der Variante "QUANTEC6WithRandom"). Dieser erzeugt echte Zufallsbits basierend auf physikalischem Rauschen (Quantenrauschen einer Zener-Diode oder Schottky-Diode als Rauschquelle).

### 5.2 Signalweg

```
Rauschquelle (Zener-/Schottky-Diode)
    ↓ Verstaerker
    ↓ Komparator (analog → digital)
    ↓
FTDI-Chip Eingangspins (D0-D3 im BitBang-Modus)
    ↓ FT_Read / ReadBits / ReadUInt8
    ↓
Software: bitBuffer → SelectionDiode → Scan-Algorithmus
```

### 5.3 Signalqualitaet

Die Software prueft kontinuierlich die Qualitaet des Rauschsignals:
- `CheckSignalQuality` -- Pruefungs-Routine
- `signalQuality` -- Aktueller Qualitaetswert
- `signalDropout` -- Erkennung von Signal-Aussetzern
- Wenn die Qualitaet zu schlecht ist → Fehlermeldung "Diode Error"

---

## 6. Machbarkeitsbewertung: Mac-Version

### 6.1 Was fuer eine Mac-Version benoetigt wird

| Komponente | Windows Original | Mac-Aequivalent | Machbarkeit |
|-----------|-----------------|-----------------|-------------|
| **UI-Framework** | WPF/XAML | SwiftUI oder Electron | Hoch (Neuentwicklung) |
| **Datenbank** | Proprietaer .store | PostgreSQL + pgvector (fertig) | Erledigt |
| **FTDI-Treiber** | ftd2xx.dll (Windows) | libftd2xx.dylib (macOS) | Hoch (FTDI liefert Mac-Treiber) |
| **BitBang-API** | FT_SetBitMode etc. | Identische API in libftd2xx | Hoch (1:1 portierbar) |
| **Scan-Algorithmus** | SelectionDiode (C#) | Portierung nach Swift/Python | Mittel (IL-Code analysierbar) |
| **Sende-Algorithmus** | DistributionDiode (C#) | Portierung nach Swift/Python | Mittel (IL-Code analysierbar) |
| **Lizenz-Pruefung** | FTID_GetChipIDFromHandle | Identische Funktion in macOS-API | Hoch |
| **Morphische Felder** | In .store-DB | In PostgreSQL (fertig) | Erledigt |
| **Berichte/PDF** | Aspose.Pdf | Swift: PDFKit / Python: ReportLab | Hoch |
| **Netzwerk** | WCF/TCP | Standard HTTP/WebSocket | Hoch |

### 6.2 Was JETZT schon moeglich ist

Ja, eine Mac-Version ist grundsaetzlich machbar. Was wir haben:

**Erledigt:**
- Datenbank vollstaendig migriert (117K Items, 256 Kategorien, pgvector)
- Semantische Suche funktioniert
- Beziehungstabellen angelegt
- Alle Dateiformate entschluesselt (XOR-Key, STOR/BLOC-Format)
- Software komplett deobfuskiert (alle 9 Assemblies)
- Hardware-Schnittstelle dokumentiert (FTDI D2XX API)

**Noch offen:**
1. **FTDI D2XX Mac-Treiber** testen (`libftd2xx.dylib` von ftdichip.com)
2. **Scan-Algorithmus** aus dem IL-Code der SelectionDiode rekonstruieren (ReadBits → Auswahl-Logik)
3. **Sende-Algorithmus** aus DistributionDiode rekonstruieren (Datenformat → FT_Write)
4. **UI komplett neu entwickeln** (groesster Aufwand)
5. **Butler-Logik** portieren (automatische HealingSheet-Verlaengerung)

### 6.3 Empfohlener Technologie-Stack fuer Mac

| Schicht | Empfehlung | Begruendung |
|---------|------------|-------------|
| **UI** | Electron + React | Schnellste Cross-Platform-Entwicklung, Web-Skills wiederverwendbar |
| **Backend** | Python | Bestehende Scripts, sentence-transformers, psycopg |
| **Datenbank** | PostgreSQL + pgvector | Bereits aufgebaut und befuellt |
| **FTDI** | Python + libftd2xx | python-ftdi1 oder pyftdi Library |
| **PDF** | ReportLab oder WeasyPrint | Python-native PDF-Erzeugung |

### 6.4 Risiken

| Risiko | Schwere | Mitigation |
|--------|---------|------------|
| Scan-Algorithmus nicht vollstaendig rekonstruierbar | Hoch | IL-Code der SelectionDiode Methode fuer Methode analysieren |
| FTDI-Lizenz an Windows-Chip-ID gebunden | Mittel | ChipID ist hardware-basiert, funktioniert auch unter macOS |
| Sende-Datenformat unbekannt | Mittel | DistributionDiode IL-Code analysieren oder USB-Sniffer |
| Kein physisches Geraet zum Testen | Hoch | Mockup-Modus fuer Entwicklung, echte Tests erst mit Geraet |

---

## 7. Naechste Schritte

1. **IL-Code-Analyse** der SelectionDiode und DistributionDiode Methoden (kann mit dem deobfuskierten Code auf einem Windows-System mit dnSpy gemacht werden)
2. **FTDI Mac-Treiber** testen: `brew install libftdi` oder FTDI D2XX von ftdichip.com
3. **Prototyp**: Python-Script das ueber libftd2xx eine FTDI-Diode im BitBang-Modus anspricht
4. **UI-Prototyp**: Electron-App mit den bestehenden PostgreSQL-Daten
