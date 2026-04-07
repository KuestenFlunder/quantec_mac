# QUANTEC PRO Mac -- Vollstaendiger Implementierungsplan

**Datum**: 2026-04-05
**Ziel**: Neuimplementierung der QUANTEC PRO Software als native Mac-Anwendung
**Kontext**: Originalquellcode nicht verfuegbar, vollstaendiges Reverse Engineering abgeschlossen

---

## 1. Ausgangslage

### 1.1 Was wir haben

| Artefakt | Pfad | Beschreibung |
|----------|------|-------------|
| **Funktionale Spezifikation** | `claudedocs/QUANTEC_PRO_Funktionale_Spezifikation.md` | 16 Kapitel: Workflow, HealingSheet-Format, Scan, Send, Module, UI |
| **Hardware-Analyse** | `claudedocs/QUANTEC_Hardware_Reverse_Engineering.md` | FTDI-API, Pin-Belegung, Chip-Typen, Lizenzmechanismus |
| **Scan/Send-Algorithmus** | `claudedocs/QUANTEC_Scan_Send_Algorithmus.md` | 5 Scan-Varianten + Send-Protokoll, komplett als C# dekompiliert |
| **Dekompilierter C# Code** | `claudedocs/deobfuscated/Hardware.decompiled.cs` | 1.751 Zeilen, vollstaendige FTDI-Kommunikation |
| **9 Deobfuskierte DLLs** | `claudedocs/deobfuscated/*.dll` | Core, Hardware, Foundation, Storage, Network, License, Migration, Scopes, CoreServices |
| **Vektor-Datenbank** | `quantec_vector/` (Docker Port 5434) | 117.030 Items, 256 Kategorien, pgvector Embeddings, semantische Suche |
| **Migrations-Datenbank** | `quantec_migration/` (Docker Port 5433) | 861.088 raw_blocks, Transferschicht mit allen Rohdaten |
| **DB-Dokumentation** | `claudedocs/QUANTEC_Migration_Dokumentation.md` | XOR-Key, STOR/BLOC-Format, Schema, Import-Pipeline |
| **Setup-Anleitung** | `claudedocs/QUANTEC_Setup_und_Gebrauchsanweisung.md` | Docker, CLI, SQL-Queries, Verbindungsdaten |
| **Original .store** | `_QUANTEC PRO/QUANTEC PRO.store` | 1.84 GB Originaldatenbank (XOR-verschluesselt) |
| **Original .exe** | `_QUANTEC PRO/QUANTEC PRO.exe` | 6.2 MB .NET 4.0 WPF (SmartAssembly geschuetzt) |
| **Original Handout** | `_QUANTEC PRO/Handout_DE.pdf` | Deutsche Benutzer-Dokumentation |

### 1.2 Technologie-Entscheidungen

| Entscheidung | Wahl | Begruendung |
|-------------|------|-------------|
| **UI-Framework** | Electron + React | Cross-Platform, schnelle Entwicklung, Web-Skills |
| **Backend** | Python (FastAPI) | Bestehende Scripts, sentence-transformers, psycopg |
| **Datenbank** | PostgreSQL 16 + pgvector | Bereits aufgebaut, semantische Suche funktioniert |
| **FTDI-Treiber** | pyftdi oder python-ftd2xx | Direkte Portierung der dekompilierten Hardware.dll |
| **PDF-Erzeugung** | WeasyPrint oder ReportLab | Python-native, keine externe Abhaengigkeit |
| **Sprache** | Deutsch (primaer), Englisch (sekundaer) | Aus dem Original extrahierbar |

---

## 2. Architektur

```
┌─────────────────────────────────────────────────────┐
│  Electron App (Renderer)                             │
│  ┌─────────────────────────────────────────────────┐ │
│  │  React Frontend                                  │ │
│  │  ├── ClientView      (Klientenverwaltung)       │ │
│  │  ├── TargetView      (Zielobjekte)              │ │
│  │  ├── HealingSheetEditor (Sheet + Items)         │ │
│  │  ├── MorphicFieldBrowser (Wissensdatenbank)     │ │
│  │  ├── ScanView        (Scanner + Ergebnisse)     │ │
│  │  ├── ScheduleView    (Sendeplaner/Kalender)     │ │
│  │  ├── SendView        (Bewellungs-Animation)     │ │
│  │  ├── ModuleView      (Zahn/Reflex/Wirbel)      │ │
│  │  ├── ReportsView     (Berichte + PDF)           │ │
│  │  └── SettingsView    (Einstellungen)            │ │
│  └─────────────────────────────────────────────────┘ │
│         │ IPC (JSON)                                  │
│  ┌──────▼──────────────────────────────────────────┐ │
│  │  Electron Main Process                           │ │
│  │  ├── Python Backend Launcher                    │ │
│  │  └── FTDI Native Bridge (optional)              │ │
│  └──────┬──────────────────────────────────────────┘ │
└─────────┼───────────────────────────────────────────┘
          │ HTTP REST API (localhost:8000)
┌─────────▼───────────────────────────────────────────┐
│  Python Backend (FastAPI)                            │
│  ├── api/                                            │
│  │   ├── clients.py     (CRUD Client)               │
│  │   ├── targets.py     (CRUD Target)               │
│  │   ├── sheets.py      (CRUD HealingSheet + Items) │
│  │   ├── morphic.py     (Browse + Search)           │
│  │   ├── scan.py        (Scan-Steuerung)            │
│  │   ├── send.py        (Sende-Steuerung)           │
│  │   ├── schedule.py    (Zeitplan-Management)       │
│  │   └── reports.py     (PDF-Erzeugung)             │
│  ├── hardware/                                       │
│  │   ├── ftdi.py        (FTDI D2XX Wrapper)         │
│  │   ├── diode.py       (BasicDiode, Scan, Send)    │
│  │   └── signal.py      (Signalqualitaet)           │
│  ├── search/                                         │
│  │   ├── semantic.py    (pgvector Embedding-Suche)  │
│  │   ├── fulltext.py    (GIN Volltext-Suche)        │
│  │   └── hybrid.py      (Kombinierte Suche)         │
│  └── models/                                         │
│      ├── client.py      (SQLAlchemy Models)         │
│      ├── target.py                                   │
│      ├── healing_sheet.py                            │
│      ├── morphic_field.py                            │
│      └── schedule.py                                 │
│         │                                            │
│         ▼                                            │
│  ┌─────────────────────────────────────┐             │
│  │  PostgreSQL 16 + pgvector            │             │
│  │  ├── esoteric_item (117K + Embeddings)            │
│  │  ├── client / target                 │             │
│  │  ├── healing_sheet / _item           │             │
│  │  ├── schedule / send_job             │             │
│  │  ├── category / category_relation    │             │
│  │  └── item_relation                   │             │
│  └─────────────────────────────────────┘             │
│         │                                            │
│  ┌──────▼──────────────────┐                         │
│  │  FTDI USB Hardware       │                         │
│  │  FT232R (BitBang Mode)   │                         │
│  │  Pin D1: Rauscheingang   │                         │
│  │  Pin D4: Diode ON/OFF    │                         │
│  └─────────────────────────┘                         │
└──────────────────────────────────────────────────────┘
```

---

## 3. Datenbank-Schema (Produktions-DB)

### 3.1 Bestehende Tabellen (bereits in quantec_vector_db)

```sql
-- Bereits befuellt und funktionsfaehig:
theme              (24 Rows)   -- Themengebiete
category           (256 Rows)  -- Kategorien mit Hierarchie
esoteric_item      (117.030)   -- Morphische Felder mit Embeddings (768 Dim)
category_relation  (1.388)     -- Keyword-basierte Beziehungen
item_relation      (0)         -- Vorbereitet fuer Item-Beziehungen
import_log         (1)         -- Import-Protokoll
```

### 3.2 Neue Tabellen (muessen erstellt werden)

```sql
-- Client-Verwaltung (aus Transferschicht migrierbar: 302 Rows)
CREATE TABLE client (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(200),
    last_name VARCHAR(200),
    title VARCHAR(50),          -- Dr., Prof.
    salutation VARCHAR(50),     -- Herr, Frau, Firma
    letter_salutation TEXT,     -- "Sehr geehrte Frau..."
    email VARCHAR(300),
    phone_home VARCHAR(50),
    phone_business VARCHAR(50),
    phone_mobile VARCHAR(50),
    address_street TEXT,
    address_zip VARCHAR(20),
    address_city VARCHAR(200),
    address_country CHAR(2),
    date_of_birth DATE,
    gender VARCHAR(10),         -- Male, Female, Neutral
    insurance VARCHAR(200),
    photo BYTEA,
    notes TEXT,
    first_contact DATE,
    last_contact DATE,
    reminder_date DATE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Zielobjekte (migrierbar: 2.107 Rows)
CREATE TABLE target (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    name VARCHAR(400),
    target_type VARCHAR(50) DEFAULT 'Person',  -- Person, Tier, Ort
    gender VARCHAR(10),
    date_of_birth DATE,
    photo1 BYTEA,
    photo2 BYTEA,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE,
    reminder_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- HealingSheets
CREATE TABLE healing_sheet (
    id SERIAL PRIMARY KEY,
    target_id INTEGER NOT NULL REFERENCES target(id) ON DELETE CASCADE,
    name VARCHAR(400),
    send_type VARCHAR(30) DEFAULT 'AnimatedWithMedia',
    sort_order VARCHAR(20) DEFAULT 'ByName',
    use_hs_picture BOOLEAN DEFAULT FALSE,
    use_target_picture BOOLEAN DEFAULT TRUE,
    has_advice BOOLEAN DEFAULT FALSE,
    advice_text TEXT,              -- Affirmation
    is_template BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    expiry_date DATE,
    photo BYTEA,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- HealingSheet Items
CREATE TABLE healing_sheet_item (
    id SERIAL PRIMARY KEY,
    healing_sheet_id INTEGER NOT NULL REFERENCES healing_sheet(id) ON DELETE CASCADE,
    sort_index INTEGER DEFAULT 0,
    text TEXT NOT NULL,
    comment TEXT,
    potency_kind VARCHAR(5),      -- C, D, LM
    potency_value INTEGER,        -- z.B. 30, 200, 12
    potency_intensity REAL,
    qrs_factor REAL,
    color VARCHAR(10),            -- Red, Blue, Green, Yellow, None
    media_data BYTEA,
    suppress_printing BOOLEAN DEFAULT FALSE,
    ignore_on_check BOOLEAN DEFAULT FALSE,
    do_not_extend BOOLEAN DEFAULT FALSE,
    mistake_count INTEGER DEFAULT 0,
    changed_by_butler BOOLEAN DEFAULT FALSE,
    morphic_field_item_id BIGINT REFERENCES esoteric_item(id),  -- Herkunft
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sendepläne
CREATE TABLE schedule (
    id SERIAL PRIMARY KEY,
    healing_sheet_id INTEGER NOT NULL REFERENCES healing_sheet(id) ON DELETE CASCADE,
    schedule_type VARCHAR(20) NOT NULL,  -- Direct, Single, Interval, Random, SMS
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    interval_duration INTERVAL DEFAULT '3 hours',
    send_duration INTERVAL DEFAULT '12 seconds',
    active BOOLEAN DEFAULT TRUE,
    butler_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Einzelne Sendeauftraege
CREATE TABLE send_job (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL REFERENCES schedule(id) ON DELETE CASCADE,
    scheduled_start TIMESTAMPTZ NOT NULL,
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    duration INTERVAL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, cancelled
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Hardware-Schicht (FTDI)

### 4.1 Referenz-Implementierung

Die komplette Hardware-Kommunikation ist dekompiliert in:
**`claudedocs/deobfuscated/Hardware.decompiled.cs`** (1.751 Zeilen C#)

### 4.2 Python-Portierung: `hardware/ftdi.py`

```python
# Kern-Konstanten (aus dem dekompilierten Code)
BAUD_RATE = 57600
PIN_MASK_ON = 0x34     # D2+D4+D5 als Ausgang
PIN_MASK_OFF = 0x37    # D0+D1+D2+D4+D5 als Ausgang
CMD_DIODE_ON = 0x10    # DTR HIGH
CMD_DIODE_OFF = 0x14   # DTR+RTS HIGH
NOISE_BIT = 0x02       # Bit 1 (RXD) = Rauschsignal
DEFAULT_AVERAGE = 11   # Samples pro Output-Bit
BUFFER_SIZE = 4096
SIGNAL_QUALITY_THRESHOLD = 0.002
WARMUP_ROUNDS = 42
DROPOUT_RECOVERY_ROUNDS = 14
```

### 4.3 Scan-Algorithmen (5 Varianten)

Alle 5 sind vollstaendig dekompiliert (siehe `QUANTEC_Scan_Send_Algorithmus.md`):

| Klasse | DiodeType Enum | Verwendung | Algorithmus |
|--------|---------------|------------|-------------|
| **SelectionDiode** | Selection (4) | Standard-Scan | ReadBits → sequentielles Durchlaufen → Normalisierung |
| **QUANTEC6Diode** | QUANTEC6 (0) | Bit-Extraktion | ReadUInt8 → Bits extrahieren → kumulativer Walk |
| **QUANTEC6DiodeWithRandom** | QUANTEC6WithRandom (1) | Hardware+Software | Wie QUANTEC6 + random.Next() |
| **DistributionDiode** | Distribution (3) | Verteilungs-Scan | ReadUInt32 → (sum*N)>>32 → Gleichverteilung |
| **RemainderDiode** | Remainder (2) | Rest-Scan | XOR uint64 → Potenz-Iteration → Modulo |

### 4.4 Send-Protokoll

```python
def send(duration_seconds):
    """Bewellung: Rauschgenerator fuer die Dauer aktivieren."""
    device.begin_read(quality=True)   # Diode EIN + Signalcheck
    end_time = time.time() + duration_seconds
    while time.time() < end_time:
        device.read_bytes(1024)       # Rauschbits lesen (verwerfen)
    device.end_read()                 # Diode AUS
```

**Klarstellung**: Beim Senden werden KEINE Daten an die Diode uebertragen. Die Diode erzeugt Rauschen waehrend auf dem Bildschirm das HealingSheet visuell dargestellt wird (ScrollEffect + TextOverlay + Fade + MediaPlayer). Das ist das Konzept der Radionik.

### 4.5 Hardware-Alternative (ohne Original-Dongle)

Ein **Standard FTDI FT232R Breakout-Board** (Sparkfun/Adafruit, ~15 EUR) mit einer **Zener-Dioden-Rauschschaltung** an Pin D1 (RXD) funktioniert identisch. Die Lizenzpruefung (`FTID_GetChipIDFromHandle`) entfaellt in unserer Software.

Minimalschaltung:
```
+5V ──┬── 10kΩ ──┬── Pin D1 (RXD)
      │          │
      Zener 5.1V (rueckwaerts)
      │
     GND
```

---

## 5. Implementierungs-Phasen

### Phase 1: Grundgeruest (Backend + DB)

**Ziel**: Lauffaehiges Backend mit REST API, DB-Anbindung

**Tasks:**
1. FastAPI Projekt aufsetzen (`quantec_app/`)
2. SQLAlchemy Models fuer alle Tabellen (Abschnitt 3)
3. Alembic Migrations
4. CRUD API Endpoints: `/clients`, `/targets`, `/sheets`, `/items`
5. Morphische-Feld-Browser: `/morphic/search`, `/morphic/categories`
6. Bestehende 117K Items + Kategorien ueber quantec_vector_db anbinden

**Referenzen:**
- Schema: Abschnitt 3.2 dieses Dokuments
- Bestehendes Schema: `quantec_vector/init-db/01_schema.sql`
- Embedding-Suche: `quantec_vector/scripts/search.py`

### Phase 2: Hardware-Schicht (FTDI + Scan + Send)

**Ziel**: FTDI-Kommunikation auf Mac, Scan funktioniert

**Tasks:**
1. `pyftdi` installieren und testen (kein FTDI-Geraet noetig fuer Mock)
2. `hardware/ftdi.py` -- FTDI D2XX Wrapper (portiert aus `Hardware.decompiled.cs` Zeile 32-440)
3. `hardware/diode.py` -- BasicDiode + alle 5 Scan-Varianten (Zeile 808-1305)
4. `hardware/signal.py` -- Signalqualitaets-Pruefung (Zeile 139-155)
5. Mock-Modus fuer Entwicklung ohne physische Diode
6. Unit-Tests mit simulierten Zufallsdaten

**Referenzen:**
- Dekompilierter Code: `claudedocs/deobfuscated/Hardware.decompiled.cs`
- Pin-Belegung: `QUANTEC_Scan_Send_Algorithmus.md` Abschnitt 1
- Algorithmen: `QUANTEC_Scan_Send_Algorithmus.md` Abschnitt 3+4

### Phase 3: Electron Frontend (Basis-UI)

**Ziel**: Navigierbare App mit Klienten/Target/Sheet-Verwaltung

**Tasks:**
1. Electron + React + TypeScript Projekt aufsetzen
2. Navigation: Sidebar mit allen 10+ Bereichen
3. ClientView: Liste + Detail + CRUD
4. TargetView: Pro Client, mit Foto-Upload
5. HealingSheetEditor: Items-Tabelle mit Potenz/QRS/Farbe
6. MorphicFieldBrowser: Kategoriebaum + semantische Suche
7. Styling: Blau-basiertes Theme (aus Original-Settings)

**Referenzen:**
- UI-Bereiche: `QUANTEC_PRO_Funktionale_Spezifikation.md` Abschnitt 13
- Theme-Farben: `_QUANTEC PRO/QUANTEC PRO.settings` (RGB-Werte)
- Benutzer-Handbuch: `_QUANTEC PRO/Handout_DE.pdf`

### Phase 4: Scan + Send Integration

**Ziel**: Vollstaendiger Scan-Workflow und Bewellung

**Tasks:**
1. ScanView: Morphische-Feld-Auswahl → Start → Ergebnisse → Uebernahme ins Sheet
2. SendView: HealingSheet-Animation (ScrollEffect + TextOverlay + Fade)
3. Sendeplaner: Kalenderansicht, Intervall/Random/Direct/Single Modi
4. SendJob-Verwaltung: Queue, Status, Historie
5. Dioden-Status-Anzeige (Logo im Footer)

**Referenzen:**
- Scan-Ablauf: `QUANTEC_PRO_Funktionale_Spezifikation.md` Abschnitt 6
- Send-Modi: `QUANTEC_PRO_Funktionale_Spezifikation.md` Abschnitt 5
- Animation: Original nutzt HLSL Shader (`effects/scrolleffect.fx`) → CSS-Animationen

### Phase 5: Erweiterte Features

**Ziel**: Berichte, Module, Butler

**Tasks:**
1. PDF-Berichte (18 Typen): WeasyPrint Templates
2. Zahnmodul: SVG-basierte Zahnstatus-Ansicht
3. Reflexzonenmodul: 8 Fuss-Ansichten als SVG
4. Wirbelsaeulenmodul: Wirbelstatus als SVG
5. Butler-Service: Hintergrund-Thread fuer HealingSheet-Ueberwachung
6. Import/Export: Morphische Felder (XML), ExpertScans

---

## 6. Konfiguration

### 6.1 Standard-Konfigurationswerte (aus Original)

```json
{
  "scan": {
    "cycles": 88,
    "maxMorphicFields": 21,
    "useGender": true,
    "keepResults": true,
    "diodeType": "QUANTEC6"
  },
  "send": {
    "type": "AnimatedWithMedia",
    "autoStart": "5min",
    "defaultInterval": "03:00:00",
    "defaultDuration": "00:00:12",
    "expiringPeriodMonths": 12
  },
  "healingSheet": {
    "showQRS": true,
    "spellChecking": true,
    "sortOrder": "ByName"
  },
  "ui": {
    "language": "de",
    "theme": "blue",
    "windowState": "maximized"
  }
}
```

### 6.2 Verbindungsdaten

```
PostgreSQL (Vektor-DB):  localhost:5434 / quantec_vector / quantec / quantec_vec_2026
PostgreSQL (Transfer):   localhost:5433 / quantec / quantec / quantec_dev_2026
FTDI USB:                /dev/tty.usbserial-* (macOS) via pyftdi
```

---

## 7. Geschaeftsregeln

### 7.1 HealingSheet-Lebenszyklus

```
ERSTELLEN → BEFUELLEN → AKTIV → [SENDEN] → ABLAUFEND → VERLAENGERT
                                    ↑              ↓
                                    └── BUTLER ────┘

Zustaende:
- Erstellt: Leeres Sheet, Name vergeben
- Befuellt: Items eingefuegt (manuell oder per Scan)
- Aktiv: Sendeplan zugewiesen, Bewellung laeuft
- Ablaufend: Expiry-Datum naeher als expiringPeriodMonths
- Verlaengert: Butler hat Items geprueft und ggf. ersetzt
- Inaktiv: Manuell deaktiviert (blau angezeigt)
- Geloescht: Im Papierkorb (wiederherstellbar)
```

### 7.2 Butler-Logik

```
Alle 5 Minuten (Issues Interval):
1. Pruefe alle aktiven HealingSheets
2. Fuer jedes ablaufende Sheet:
   a. Fuehre neuen Scan durch (mit den gleichen Morphischen Feldern)
   b. Vergleiche neue Ergebnisse mit bestehenden Items
   c. Items mit MistakeCount > 0 UND DoNotExtend = false ersetzen
   d. Markiere neue Items als "RecentlyChangedByButler"
   e. Setze neues Expiry-Datum
```

### 7.3 Scan → HealingSheet Uebernahme

```
1. Benutzer waehlt Morphische Felder (max 21) oder Scan-Vorlage
2. Scan laeuft: data[] Array mit N Slots, je cycles Durchlaeufe
3. Ergebnis: Jeder Slot hat einen Score (Treffer-Anzahl)
4. Sortierung nach Score (hoechster = relevantester)
5. Benutzer waehlt: Alle uebernehmen ODER einzelne auswaehlen
6. Uebernahme: Fuer jedes ausgewaehlte Item:
   - text = Morphisches-Feld-Item text_primary
   - morphic_field_item_id = Referenz auf esoteric_item
   - Potenz/Intensitaet: Optional per separatem Scan bestimmen
```

---

## 8. Bekannte Luecken (bewusst akzeptiert fuer V1)

| Luecke | Auswirkung | Mitigation |
|--------|-----------|------------|
| Netzwerk-Modus | Kein Multi-User | V1 ist Standalone-only, wie die aktuelle Installation |
| SMS-Trigger/App | Keine Remote-Bewellung | Spaetere Phase, nicht fuer V1 noetig |
| QUANTEC 6 Migration | Kein Import alter Daten | Nur relevant fuer Bestandskunden mit Altdaten |
| Kategorie-Baumstruktur | Flache Hierarchie statt Baum | 24 Themes → 256 Kategorien reicht fuer V1 |
| 6 weitere Sprachen | Nur DE + EN | UI-Strings spaeter uebersetzbar |
| Exakte Butler-Logik | Vereinfachte Version | Manuelles Verlaengern als Fallback |

---

## 9. Datei-Referenz-Matrix

### Fuer Phase 1 (Backend):

| Aufgabe | Referenz-Datei | Relevante Abschnitte |
|---------|---------------|---------------------|
| DB-Schema | Dieses Dokument, Abschnitt 3 | Alle CREATE TABLE Statements |
| Bestehendes Schema | `quantec_vector/init-db/01_schema.sql` | theme, category, esoteric_item |
| Entity-Modell | `QUANTEC_PRO_Funktionale_Spezifikation.md` | Abschnitt 3-5 |
| Such-API | `quantec_vector/scripts/search.py` | semantic(), fulltext(), hybrid() |
| DB-Verbindung | `quantec_vector/.env` | Connection Strings |

### Fuer Phase 2 (Hardware):

| Aufgabe | Referenz-Datei | Relevante Zeilen |
|---------|---------------|------------------|
| FTDI Wrapper | `Hardware.decompiled.cs` | 32-440 (BitBangDevice + Device) |
| BasicDiode | `Hardware.decompiled.cs` | 808-919 |
| SelectionDiode (Scan) | `Hardware.decompiled.cs` | 1237-1305 |
| QUANTEC6Diode (Scan) | `Hardware.decompiled.cs` | 1028-1129 |
| QUANTEC6+Random (Scan) | `Hardware.decompiled.cs` | 1130-1236 |
| DistributionDiode (Scan) | `Hardware.decompiled.cs` | 920-967 |
| RemainderDiode (Scan) | `Hardware.decompiled.cs` | 968-1027 |
| Send-Protokoll | `Hardware.decompiled.cs` | 859-890 |
| Signalqualitaet | `Hardware.decompiled.cs` | 139-155 |
| Pin-Belegung | `QUANTEC_Scan_Send_Algorithmus.md` | Abschnitt 1 |

### Fuer Phase 3 (UI):

| Aufgabe | Referenz-Datei | Relevante Abschnitte |
|---------|---------------|---------------------|
| UI-Bereiche | `QUANTEC_PRO_Funktionale_Spezifikation.md` | Abschnitt 13 |
| Theme-Farben | `_QUANTEC PRO/QUANTEC PRO.settings` | `<Theme>` Block (35 RGB-Werte) |
| HealingSheet-Editor | `QUANTEC_PRO_Funktionale_Spezifikation.md` | Abschnitt 4 |
| Hilfetexte (EN) | `_QUANTEC PRO/QUANTEC PRO.exe` | Eingebettete Translations |
| Benutzer-Handbuch | `_QUANTEC PRO/Handout_DE.pdf` | Screenshots, Workflows |

### Fuer Phase 4 (Scan/Send):

| Aufgabe | Referenz-Datei |
|---------|---------------|
| Scan-Ablauf | `QUANTEC_PRO_Funktionale_Spezifikation.md` Abschnitt 6 |
| Scan-Konfiguration | `_QUANTEC PRO/QUANTEC PRO.settings` (`<Scan>` Block) |
| Send-Animation | CSS-Portierung von `effects/scrolleffect.fx` (HLSL Shader) |
| Sendeplaner | `QUANTEC_PRO_Funktionale_Spezifikation.md` Abschnitt 5.4 |

---

## 10. Validierung: Kann ein frischer Context die App bauen?

### Ja, mit folgenden Voraussetzungen:

**Muss mitgegeben werden:**
1. Dieses Dokument (`QUANTEC_MAC_Implementierungsplan.md`)
2. `claudedocs/deobfuscated/Hardware.decompiled.cs` (1.751 Zeilen, komplette FTDI-Logik)
3. `quantec_vector/init-db/01_schema.sql` (bestehendes DB-Schema)
4. `quantec_vector/.env` (Verbindungsdaten)
5. Zugriff auf laufenden Docker-Container `quantec_vector_db` (Port 5434)

**Kann in Session erfragt werden:**
- `QUANTEC_PRO_Funktionale_Spezifikation.md` fuer UI-Details
- `QUANTEC_Scan_Send_Algorithmus.md` fuer Hardware-Details
- `_QUANTEC PRO/QUANTEC PRO.settings` fuer Konfigurationswerte

**Nicht noetig fuer V1:**
- Die Original .exe oder .store Dateien
- Die Transferschicht (quantec_migration)
- Die Rohdaten (raw_blocks)

### Geschaetzter Aufwand pro Phase:

| Phase | Aufwand | Ergebnis |
|-------|---------|----------|
| Phase 1: Backend + DB | 1-2 Sessions | Lauffaehige REST API mit CRUD |
| Phase 2: FTDI + Scan | 1 Session | Hardware-Mock + Scan-Algorithmus |
| Phase 3: Electron UI | 2-3 Sessions | Navigierbare App mit Datenverwaltung |
| Phase 4: Scan/Send UI | 1-2 Sessions | Vollstaendiger Scan+Send Workflow |
| Phase 5: Reports etc. | 2-3 Sessions | PDF-Berichte, Module, Butler |

**Gesamt: 7-11 Sessions fuer eine funktionsfaehige V1.**
