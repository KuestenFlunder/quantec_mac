# QUANTEC PRO -- Datenbank-Migration Dokumentation

**Datum**: 2026-04-04
**Projekt**: Migration der QUANTEC PRO Windows-Anwendung auf macOS
**Phase**: Datenbank-Reverse-Engineering und PostgreSQL-Migration
**Status**: Datenbank vollstaendig migriert und kategorisiert

---

## 1. Ausgangslage

QUANTEC PRO ist eine .NET 4.0 WPF Desktop-Anwendung zur Steuerung eines Bioresonanzgeraets (QUANTEC 6). Der urspruengliche Entwickler ist nicht mehr im Unternehmen, der Quellcode ist nicht verfuegbar. Die Anwendung speichert saemtliche Daten in einer proprietaeren `.store`-Datei.

**Verfuegbare Dateien:**
- `QUANTEC PRO.exe` -- 6.2 MB, .NET 4.0 WPF, obfuskiert mit SmartAssembly 6.9.0.114
- `QUANTEC PRO.store` -- 1.84 GB, proprietaere verschluesselte Datenbank
- `QUANTEC PROalt.store` -- 6.1 MB, aeltere/leere Template-Datenbank
- `Aspose.Pdf.dll` -- PDF-Engine
- Diverse Log-Backups, FTDI-Treiber, Konfigurationsdateien

---

## 2. Reverse Engineering Ergebnisse

### 2.1 Verschluesselung geknackt

Die `.store`-Dateien verwenden eine **XOR-Verschluesselung mit einem festen 16-Byte-Schluessel**:

```
Key (hex): bd ee ea c7 35 a5 64 6b 15 d8 3e 64 bb 89 df 93
```

Erkennungsmethode: Die sich wiederholenden 16-Byte-Bloecke an Nullstellen der Datei ergaben den Schluessel. Nach XOR-Entschluesselung erscheint der Header `STOR` und die Block-Marker `BLOC`.

### 2.2 Dateiformat: STOR/BLOC

```
.store-Datei Aufbau:
+----------------------------------+
| STOR Header (32 Bytes)           |
|   Magic: "STOR" + Metadaten     |
+----------------------------------+
| BLOC Record #1 (variabel)       |
|   [0:4]   "BLOC" Magic          |
|   [4:8]   Hash (uint32 LE)      |
|   [8:12]  Type-ID (uint32 LE)   |   <-- Entitaetstyp + Kategorie
|   [12:14] Sequenz (uint16 LE)   |
|   [14:32] Metadaten             |
|   [32:N]  Payload (Text/Daten)  |
+----------------------------------+
| BLOC Record #2 ...               |
| ...                              |
+----------------------------------+
| DOWN (Index-Tabelle)             |
| DOWN (Dateiende-Marker)          |
+----------------------------------+
```

**Typ-ID Kodierung** (Schluesselentdeckung):
- Unteres Byte = Entity-Typ (z.B. 0x57 = MorphicFieldItem)
- Oberes Byte = Kategorie-ID (z.B. 0x27 = Koran, 0x5f = ICD-10)
- Alle esoterischen Datenkatalog-Eintraege teilen sich Entity-Typ 0x57 oder 0x56

### 2.3 .NET Assembly-Analyse

Aus String-Extraktion der `QUANTEC PRO.exe` wurden identifiziert:
- **Assemblies**: Core (v1.0), CoreServices (v1.0), License (v1.0), Migration (v1.0)
- **Entity-Modell**: Client, Target, HealingSheet, HealingSheetItem, MorphicField, MorphicFieldItem, Schedule, SendJob, Account
- **Module**: Dental, Reflex, Spinal, ExpertScan
- **13 Enum-Typen**: Gender, Potency (C/D/LM), SendType, ScheduleType, etc.
- **Hardware**: FTDI USB (QUANTEC6 Geraet), UART seriell
- **Netzwerk**: FTP-Updates via servicecenter.quantec.eu, Central-Server-Mode

---

## 3. Migration nach PostgreSQL

### 3.1 Infrastruktur

**Docker-Setup** (`quantec_migration/docker-compose.yml`):
- PostgreSQL 16 Alpine (Port 5433, weil 5432 belegt)
- pgAdmin 4 (Port 5050)
- Tuning: shared_buffers=512MB, work_mem=64MB, max_wal_size=2GB

**Zugriff:**
- psql: `docker exec -it quantec_db psql -U quantec`
- pgAdmin: http://localhost:5050 (admin@quantec.local / admin)
- Python CLI: `.venv/bin/python -m src.cli`

### 3.2 Python-Pipeline

**Projektstruktur** (`quantec_migration/`):
```
quantec_migration/
  docker-compose.yml           # PostgreSQL 16 + pgAdmin
  .env                         # Credentials (Port 5433)
  init-db/
    01_create_tables.sql        # 10 Tabellen + ENUMs
    02_create_indexes.sql       # Indizes + Full-Text-Search
    03_create_views.sql         # 6 Analyse-Views
  src/
    config.py                   # XOR-Key, Pfade, Typ-Registry, Kategorie-Namen
    decryptor.py                # Streaming XOR (64KB Chunks)
    bloc_parser.py              # BLOC-Record-Scanner (Generator-basiert)
    field_extractor.py          # String-Extraktion aus Payloads (UTF-8)
    db/
      connection.py             # psycopg3 Verbindung
      importer.py               # Batch-Import (COPY + executemany)
    cli.py                      # Click-CLI: import-db, stats, search
  requirements.txt              # psycopg[binary], click, tqdm, python-dotenv
  .venv/                        # Python 3.14 Virtual Environment
```

**Pipeline-Ablauf:**
1. `decryptor.py` liest die .store-Datei in 64KB-Chunks und entschluesselt per XOR
2. `bloc_parser.py` scannt den entschluesselten Stream nach BLOC-Markern (16-Byte-aligned)
3. `field_extractor.py` extrahiert lesbare UTF-8 Strings aus den Payloads
4. `importer.py` routet Records nach Typ-ID in die richtige Tabelle und fuegt per Batch ein

**Laufzeit**: ~4 Minuten fuer 1.84 GB (Parsing + Import)

### 3.3 Datenbank-Schema

**10 Tabellen:**

| Tabelle | Rows | Beschreibung |
|---------|-----:|-------------|
| `raw_blocks` | 861.088 | Alle Records roh (Safety-Net) |
| `morphic_field_item` | 117.030 | Esoterische Wissensdatenbank |
| `address_pos` | 58.030 | PLZ AT/DE |
| `target` | 2.107 | Behandlungsziele |
| `client` | 302 | Klienten |
| `morphic_field_category` | 29 | Vordefinierte Kategorien |
| `db_metadata` | 1 | Import-Metadaten |
| `healing_sheet` | 0 | (noch nicht geparst) |
| `healing_sheet_item` | 0 | (noch nicht geparst) |
| `media_blob` | 0 | (Import uebersprungen, ~15K Bilder) |

**6 ENUMs:** gender_type, potency_kind, highlight_color, send_type, schedule_type, hs_sort_order

**6 Views:** v_import_overview, v_type_distribution, v_plz_stats, v_esoteric_categories, v_category_samples, v_media_stats

### 3.4 Verifizierung (Goldstandard)

| Test | Erwartet | Ergebnis |
|------|----------|----------|
| PLZ 1010 | AT / Wien | OK |
| PLZ 1011 | AT / Wien Postfach | OK |
| PLZ 1017 | AT / Wien-Parlament | OK |
| Client Musterfrau | Salutation "Sehr geehrte Frau Musterfrau" | OK |
| DB-Version | 11800 | OK |
| Koran Sura 1 | "Sura zur Eroeffnung des Buches..." | OK |
| Homoeopathie | "Abies canadensis" | OK |
| Edelsteine | "Achat" | OK |

---

## 4. Inhaltsanalyse: Die esoterische Wissensdatenbank

### 4.1 Gesamtueberblick

Die QUANTEC PRO Datenbank enthaelt **117.030 esoterische Datenbank-Eintraege** in **256 vollstaendig benannten Kategorien**, gegliedert in **26 Themengebiete**.

Zusaetzlich: 58.030 PLZ-Eintraege (AT/DE), 302 Klienten, 2.107 Targets, ~15.000 eingebettete JPEG/PNG-Bilder (nicht importiert).

### 4.2 Themengebiete (semantisch sortiert)

| # | Themengebiet | Kategorien | Eintraege | Anteil |
|---|-------------|-----------|-----------|--------|
| 1 | Nosoden & Infektiologie | 32 | 22.885 | 19,6% |
| 2 | Affirmationen & Weisheiten | 31 | 16.373 | 14,0% |
| 3 | Homoeopathie & Praeparate | 22 | 14.989 | 12,8% |
| 4 | Religion & Spiritualitaet | 14 | 13.708 | 11,7% |
| 5 | Medizin & Genetik (ICD-10, OMIM) | 4 | 8.974 | 7,7% |
| 6 | Edelsteine & Kristalle | 8 | 5.189 | 4,4% |
| 7 | Phytotherapie & Pflanzen | 17 | 4.025 | 3,4% |
| 8 | Enzymklassifikation (EC) | 1 | 3.794 | 3,2% |
| 9 | TCM & Akupunktur | 11 | 3.400 | 2,9% |
| 10 | Tarot & Archetypen | 4 | 3.123 | 2,7% |
| 11 | Anatomie & Physiologie | 18 | 2.544 | 2,2% |
| 12 | Geobiologie & Geopathie | 4 | 2.307 | 2,0% |
| 13 | Nahrungsergaenzung & Pharma | 22 | 2.097 | 1,8% |
| 14 | Symbole & Kraftplaetze | 13 | 1.663 | 1,4% |
| 15 | Astrologie & Numerologie | 3 | 1.434 | 1,2% |
| 16 | Spirituelle Kurse (ACIM) | 2 | 1.339 | 1,1% |
| 17 | Psychologie & Sonstiges | 7 | 1.267 | 1,1% |
| 18 | Chakren & Energiearbeit | 9 | 1.147 | 1,0% |
| 19 | Alternative Heilverfahren | 4 | 1.006 | 0,9% |
| 20 | Klang & Frequenzen | 3 | 872 | 0,7% |
| 21 | Aromatherapie | 3 | 772 | 0,7% |
| 22 | Diverse Methoden | 3 | 690 | 0,6% |
| 23 | Bluetentherapie | 6 | 475 | 0,4% |
| 24 | Umwelt & Toxikologie | 3 | 290 | 0,2% |
| 25 | Farbtherapie | 1 | 269 | 0,2% |
| 26 | Sonstige | 10 | 2.358 | 2,0% |

### 4.3 Top 50 Kategorien (nach Eintraegen)

| Kategorie | Eintraege | Themengebiet |
|-----------|-----------|-------------|
| ICD-10 Krankheiten + Nosoden | 11.119 | Nosoden |
| Chromosomen/Genetik (OMIM) | 7.670 | Medizin |
| Heilungs-Affirmationen | 7.608 | Affirmationen |
| Koran (deutsch, komplett) | 7.056 | Religion |
| Bibel-Texte | 5.314 | Religion |
| Enzymklassifikation (EC) | 3.794 | Enzymklassifikation |
| Materia Medica (Detail) | 3.480 | Homoeopathie |
| Edelsteine/Kristalle | 2.819 | Edelsteine |
| Tarot/Esoterik (Katalog) | 2.228 | Tarot |
| Esoterische Liebes-Affirmationen | 2.208 | Affirmationen |
| Homoeopathie Mittel | 2.189 | Homoeopathie |
| Homoeopathie Materia Medica | 2.008 | Homoeopathie |
| TCM Meridiane / Nosoden | 1.506 | TCM |
| Homoeopathie Arzneimittel | 1.496 | Homoeopathie |
| Komplexmittel (Heel) | 1.436 | Homoeopathie |
| Heilaffirmationen (Koerper) | 1.425 | Affirmationen |
| Feinstoffliche Stoerungen | 1.335 | Geobiologie |
| Allergene + Nosoden | 1.326 | Nosoden |
| Virologie/Nosoden | 1.287 | Nosoden |
| Numerologie | 1.263 | Astrologie |
| Koerper-Affirmationen | 924 | Affirmationen |
| 5-Elemente TCM | 866 | TCM |
| TCM Funktionskreise | 789 | TCM |
| Umweltgifte/Toxikologie Nosoden | 773 | Nosoden |
| Lektionen/Kurse (ACIM) | 763 | Spirituelle Kurse |
| Veterinaer-Nosoden | 751 | Nosoden |
| Biologie/Taxonomie | 748 | Nosoden |
| Natur/Spirituelle Zitate | 706 | Affirmationen |
| Tarot + Archetypen | 691 | Tarot |
| Phytotherapie/Kraeuter | 657 | Phytotherapie |
| Edelstein-Meditationen | 653 | Edelsteine |
| Akupunktur (361 Punkte) | 621 | TCM |
| Injeel-Praeparate (Heel) | 599 | Homoeopathie |
| Heilpflanzen-Monographien | 580 | Phytotherapie |
| Tierkrankheiten/Vet-Nosoden | 579 | Nosoden |
| ACIM Lektionen (erweitert) | 576 | Spirituelle Kurse |
| Homoeopathische Rezepturen | 572 | Homoeopathie |
| Phytotherapie (erweitert) | 563 | Phytotherapie |
| Aetherische Oele Anwendung | 557 | Aromatherapie |
| Biochemie/Molekuele | 551 | Medizin |
| Parasitologie Nosoden | 538 | Nosoden |
| Homoeopathie (Sonderpraeparate) | 523 | Homoeopathie |
| Spirituelle Weisheiten | 518 | Affirmationen |
| Psychologische Themen | 507 | Psychologie |
| Musik/Klangtherapie | 490 | Klang |
| Pharmazeutische Mittel | 486 | Pharma |
| Heilerde/Mineralstoffe | 480 | Alternative Heilverfahren |
| Mykologie/Candidose Nosoden | 479 | Nosoden |
| Schuessler-Salze | 466 | Alternative Heilverfahren |
| Kraeuter-Mischungen | 457 | Phytotherapie |

### 4.4 Beispiel-Eintraege (Stichproben)

**Koran (deutsch):**
> "001. Sura zur Eroeffnung des Buches, mekkanisch, aus 7 Versen bestehend. Im Namen Gottes, des Allerbarmers, des Allbarmherzigen."

**Tarot:**
> "0 - Der Narr: Kernaussage: Sei bereit fuer einen Quantensprung! Jetzt ist es an der Zeit, alte Verhaeltnisse, Gewohnheiten oder Lebensumstaende zurueckzulassen..."

**Homoeopathie:**
> "Abies canadensis", "Abies nigra", "Abrotanum"

**Edelsteine:**
> "Achat" -- "hilft bei Bienen-, Muecken und anderen Insektenstichen"

**ICD-10:**
> "Bestimmte infektioese und parasitaere Krankheiten" -- "Adenoviren als Ursache von Krankheiten..."

---

## 5. Noch nicht migrierte Daten

| Bereich | Records | Status |
|---------|---------|--------|
| JPEG/PNG-Bilder | ~15.000 | Uebersprungen (--skip-images), ~800 MB |
| MorphicField-Katalog (0x5f52) | 104.833 | 2.228 Text-Records extrahiert, Rest = Metadaten/Referenzen |
| MorphicField-Master (0x5f00) | 13.776 | UI-Konfiguration, kein Nutzdaten-Wert |
| HealingSheets | unbekannt | Noch nicht aus raw_blocks geparst |
| Schedules/SendJobs | unbekannt | Noch nicht aus raw_blocks geparst |
| FK-Beziehungen | -- | Client→Target→HealingSheet noch nicht verknuepft |
| Restliche raw_blocks | ~611.000 | In raw_blocks fuer spaetere Analyse |

---

## 6. Technische Referenz

### Wichtige Befehle

```bash
# Docker starten/stoppen
cd quantec_migration
docker compose up -d
docker compose down

# Datenbank-Import (Hauptdatenbank, ohne Bilder)
.venv/bin/python -m src.cli import-db --skip-images

# Import mit Alt-Store (Test)
.venv/bin/python -m src.cli import-db --alt --skip-images

# Statistiken anzeigen
.venv/bin/python -m src.cli stats

# Volltextsuche
.venv/bin/python -m src.cli search "Akupunktur"

# Direkte SQL-Abfragen
docker exec -it quantec_db psql -U quantec
```

### Wichtige SQL-Queries

```sql
-- Gesamtueberblick
SELECT * FROM v_import_overview;

-- PLZ-Statistik
SELECT * FROM v_plz_stats;

-- Esoterische Kategorien
SELECT category_name, count(*) FROM morphic_field_item GROUP BY 1 ORDER BY 2 DESC;

-- Volltextsuche
SELECT category_name, text_primary, left(text_full, 200)
FROM morphic_field_item
WHERE to_tsvector('german', coalesce(text_primary,'') || ' ' || coalesce(text_full,''))
      @@ plainto_tsquery('german', 'Suchbegriff');

-- Zufaellige Stichprobe
SELECT category_name, text_primary FROM morphic_field_item ORDER BY random() LIMIT 5;

-- Typ-Verteilung in raw_blocks
SELECT * FROM v_type_distribution LIMIT 30;
```

### Verbindungsdaten

| Service | Host | Port | User | Passwort | DB |
|---------|------|------|------|----------|-----|
| PostgreSQL | localhost | 5433 | quantec | quantec_dev_2026 | quantec |
| pgAdmin | localhost | 5050 | admin@quantec.local | admin | -- |

### XOR-Schluessel

```
Hex: bd ee ea c7 35 a5 64 6b 15 d8 3e 64 bb 89 df 93
Laenge: 16 Bytes
Anwendung: Zyklisch ueber gesamte .store-Datei
Formel: decrypted[i] = encrypted[i] XOR key[i % 16]
```

---

## 7. Naechste Schritte (offen)

1. **Bilder-Import**: `--skip-images` entfernen, ~15.000 JPEG/PNG in `media_blob` laden
2. **HealingSheet-Parsing**: Typ-IDs fuer HealingSheets in raw_blocks identifizieren und parsen
3. **FK-Beziehungen**: Client→Target→HealingSheet Verknuepfungen aus Praefix-Bytes ableiten
4. **.NET Dekompilierung**: ILSpy/dnSpy + de4dot fuer vollstaendige Code-Analyse
5. **Hardware-Protokoll**: FTDI USB-Kommunikation per USB-Sniffer dokumentieren
6. **Mac-App Prototyp**: Technologie-Entscheidung (Electron/MAUI/Swift) und erste UI
