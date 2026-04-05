# QUANTEC PRO Vektor-Datenbank -- Setup und Gebrauchsanweisung

---

## 1. Ueberblick

Das System besteht aus zwei Docker-Containern:

| Container | Zweck | Port | Status |
|-----------|-------|------|--------|
| `quantec_db` | Transferschicht (Rohdaten, raw_blocks) | 5433 | Archiv |
| `quantec_vector_db` | Produktions-DB mit pgvector | 5434 | **Aktiv** |

Die **Vektor-Datenbank** enthaelt:
- 117.030 esoterische Eintraege in 256 Kategorien
- 768-dimensionale Embeddings fuer semantische Suche (pgvector HNSW-Index)
- 1.388 Kategorie-Beziehungen
- 24 Themengebiete
- Volltext-Suchindex (GIN)

---

## 2. Voraussetzungen

- **Docker Desktop** (laeuft)
- **Python 3.11+** (getestet mit 3.14)
- Die Ports **5433** und **5434** muessen frei sein

---

## 3. System starten

### Beide Container starten

```bash
cd /Users/kuestenflunderpripares/private/QUANTEC_mac

# Transferschicht (muss laufen fuer eventuelle Nachmigration)
cd quantec_migration && docker compose up -d && cd ..

# Vektor-DB (Hauptsystem)
cd quantec_vector && docker compose up -d && cd ..
```

### Nur die Vektor-DB starten (Normalfall)

```bash
cd /Users/kuestenflunderpripares/private/QUANTEC_mac/quantec_vector
docker compose up -d
```

### Status pruefen

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Erwartete Ausgabe:
```
NAMES               STATUS          PORTS
quantec_vector_db   Up X minutes    0.0.0.0:5434->5432/tcp
quantec_db          Up X minutes    0.0.0.0:5433->5432/tcp
```

### System stoppen

```bash
cd quantec_vector && docker compose down    # Vektor-DB stoppen (Daten bleiben erhalten)
cd quantec_migration && docker compose down # Transferschicht stoppen
```

---

## 4. Suche ueber die Kommandozeile

Alle Such-Befehle werden aus dem Verzeichnis `quantec_vector/` ausgefuehrt:

```bash
cd /Users/kuestenflunderpripares/private/QUANTEC_mac/quantec_vector
```

Das Python-Environment liegt unter `../quantec_migration/.venv/`. Kurzform:

```bash
PYTHON=../quantec_migration/.venv/bin/python
```

### 4.1 Semantische Suche (Vektor-Aehnlichkeit)

Findet Eintraege nach **Bedeutung**, nicht nur nach Wortlaut. Versteht Deutsch, Englisch, Latein.

```bash
$PYTHON scripts/search.py semantic "Angst und Panikattacken"
```

Ausgabe:
```
Kategorie                           Similarity  Text
----------------------------------------------------------------------------------------------------
Heilungs-Affirmationen                  83.7%  Panikstörung [episodisch paroxysmale Angst].
Veterinär-Nosoden                       82.6%  Todesangst-Panikkonflikt Nosode
Bach-Blueten Persoenlichkeitstypen      80.4%  Man gerät leicht in innere Panik ...
```

**Optionen:**
```bash
# Mehr Ergebnisse
$PYTHON scripts/search.py semantic "Schlafstörung" -n 30

# Nur innerhalb einer Kategorie
$PYTHON scripts/search.py semantic "Heilstein gegen Kopfschmerz" -c "Edelstein"

# Nur innerhalb eines Themengebiets
$PYTHON scripts/search.py semantic "Lebensangst" -t "Affirmationen"
```

### 4.2 Volltext-Suche (exakte Wortsuche)

Findet Eintraege die das **exakte Wort** enthalten. Schnell, braucht kein Embedding-Modell.

```bash
$PYTHON scripts/search.py fulltext "Akupunktur Meridian"
```

### 4.3 Hybrid-Suche (Volltext + Vektor)

Filtert zuerst per Volltext, sortiert dann nach semantischer Aehnlichkeit. Ideal fuer praezise Anfragen.

```bash
$PYTHON scripts/search.py hybrid "homöopathisches Mittel gegen Erkältung"
```

### 4.4 Statistiken

```bash
$PYTHON scripts/search.py stats
```

Ausgabe:
```
=== Uebersicht ===
  mit_embedding                117,030
  esoteric_item                117,030
  category_relation              1,388
  category                         256
  theme                             24

=== Qualitaetsverteilung ===
  A: Sehr gut (0.8+)          19,264 (16.5%) ########
  B: Gut (0.6-0.8)            23,621 (20.2%) ##########
  C: Mittel (0.4-0.6)         66,287 (56.6%) ############################
  D: Schwach (0.2-0.4)         7,773 (6.6%) ###
  E: Minimal (0-0.2)              85 (0.1%)
```

---

## 5. Direkte SQL-Abfragen

### Verbindung herstellen

```bash
# Interaktive psql-Shell
docker exec -it quantec_vector_db psql -U quantec -d quantec_vector
```

### Nuetzliche Abfragen

**Gesamtueberblick:**
```sql
SELECT * FROM v_overview;
```

**Alle Themengebiete mit Anzahl:**
```sql
SELECT * FROM v_theme_overview;
```

**Kategorien eines Themengebiets:**
```sql
SELECT c.name, c.item_count 
FROM category c 
JOIN theme t ON t.id = c.theme_id 
WHERE t.name = 'Homoeopathie & Praeparate'
ORDER BY c.item_count DESC;
```

**Eintraege einer Kategorie durchblaettern:**
```sql
SELECT text_primary, left(text_full, 200) 
FROM esoteric_item 
WHERE category_name = 'Koran (deutsch)' 
ORDER BY id 
LIMIT 20;
```

**Verwandte Kategorien finden:**
```sql
SELECT * FROM category_neighbors(
    (SELECT id FROM category WHERE name = 'Edelsteine/Kristalle')
);
```

**Volltext-Suche direkt in SQL:**
```sql
SELECT * FROM fulltext_search('Akupunktur Meridian', 20);
```

**Qualitaetsverteilung:**
```sql
SELECT * FROM v_quality_distribution;
```

**Embedding-Abdeckung pro Kategorie:**
```sql
SELECT * FROM v_embedding_coverage;
```

**Beziehungsnetzwerk:**
```sql
SELECT * FROM v_category_network LIMIT 20;
```

**Zufaellige Stichprobe:**
```sql
SELECT category_name, text_primary 
FROM esoteric_item 
ORDER BY random() 
LIMIT 5;
```

---

## 6. pgAdmin (Webinterface)

pgAdmin ist ueber den Transferschicht-Container verfuegbar:

**URL:** http://localhost:5050
**Login:** admin@quantec.local / admin

### Vektor-DB hinzufuegen

1. Rechtsklick auf "Servers" → "Register" → "Server..."
2. Tab "General": Name = "QUANTEC Vector"
3. Tab "Connection":
   - Host: `host.docker.internal`
   - Port: `5434`
   - Database: `quantec_vector`
   - Username: `quantec`
   - Password: `quantec_vec_2026`

---

## 7. Datenbankstruktur

### Tabellen

```
quantec_vector
├── theme                    24 Themengebiete (Top-Level)
├── category                256 Kategorien (mit Hierarchie-Feldern)
├── esoteric_item       117.030 Eintraege + Embeddings
├── category_relation     1.388 Kategorie-Beziehungen
├── item_relation             0 Item-Beziehungen (fuer spaeter)
└── import_log                1 Import-Protokoll
```

### esoteric_item (Haupttabelle)

| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | BIGSERIAL | Primaerschluessel |
| category_id | INTEGER FK | Verweis auf category |
| category_name | VARCHAR | Kategoriename (denormalisiert) |
| text_primary | TEXT | Haupttext/Titel |
| text_secondary | TEXT | Nebentext (oft leer) |
| text_full | TEXT | Volltext (kann laenger sein) |
| quality_score | REAL | Qualitaet 0.0-1.0 |
| embedding | vector(768) | pgvector Embedding |
| extra | JSONB | Zusatzfelder |

### category

| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | SERIAL | Primaerschluessel |
| name | VARCHAR | Kategoriename |
| theme_id | INTEGER FK | Themengebiet |
| parent_id | INTEGER FK | Eltern-Kategorie (Hierarchie) |
| depth | INTEGER | Baumtiefe |
| item_count | INTEGER | Anzahl Eintraege |

### 24 Themengebiete

| Themengebiet | Kategorien | Eintraege |
|-------------|-----------|-----------|
| Nosoden & Infektiologie | 34 | ~23.000 |
| Affirmationen & Weisheiten | 31 | ~16.000 |
| Homoeopathie & Praeparate | 28 | ~15.000 |
| Religion & Spiritualitaet | 14 | ~14.000 |
| Medizin & Genetik | 4 | ~9.000 |
| Edelsteine & Kristalle | 8 | ~5.000 |
| Phytotherapie & Pflanzen | 17 | ~4.000 |
| Enzymklassifikation | 1 | ~3.800 |
| TCM & Akupunktur | 11 | ~3.400 |
| Tarot & Archetypen | 4 | ~3.100 |
| Anatomie & Physiologie | 19 | ~2.500 |
| Geobiologie & Geopathie | 4 | ~2.300 |
| Nahrungsergaenzung & Pharma | 21 | ~2.100 |
| + 11 weitere Themengebiete | ... | ... |

---

## 8. Verbindungsdaten (Referenz)

| System | Host | Port | DB | User | Passwort |
|--------|------|------|----|------|----------|
| **Vektor-DB** | localhost | **5434** | quantec_vector | quantec | quantec_vec_2026 |
| Transferschicht | localhost | 5433 | quantec | quantec | quantec_dev_2026 |
| pgAdmin | localhost | 5050 | -- | admin@quantec.local | admin |

**Connection-Strings:**
```
# Vektor-DB (Produktiv)
postgresql://quantec:quantec_vec_2026@localhost:5434/quantec_vector

# Transferschicht (Archiv)
postgresql://quantec:quantec_dev_2026@localhost:5433/quantec
```

---

## 9. Dateien-Uebersicht

```
QUANTEC_mac/
├── _QUANTEC PRO/                        # Original Windows-Installation
│   ├── QUANTEC PRO.exe                  # .NET 4.0 WPF Anwendung
│   ├── QUANTEC PRO.store                # Originale DB (1.84 GB, verschluesselt)
│   └── ...
│
├── quantec_migration/                    # Transferschicht
│   ├── docker-compose.yml               # PostgreSQL 16, Port 5433
│   ├── .venv/                           # Python 3.14 + Dependencies
│   ├── init-db/                         # Legacy-Schema
│   └── src/                             # Parser-Pipeline (decryptor, bloc_parser, etc.)
│
├── quantec_vector/                       # Vektor-Datenbank (Produktiv)
│   ├── docker-compose.yml               # pgvector:pg16, Port 5434
│   ├── .env                             # Verbindungsdaten
│   ├── init-db/
│   │   ├── 01_schema.sql                # 6 Tabellen + pgvector Extension
│   │   ├── 02_indexes.sql               # HNSW, GIN, B-Tree
│   │   ├── 03_views.sql                 # 5 Analyse-Views
│   │   └── 04_functions.sql             # Such-Funktionen
│   └── scripts/
│       ├── migrate_from_source.py       # Migration Transferschicht → Vektor-DB
│       ├── generate_embeddings.py       # Embedding-Berechnung (sentence-transformers)
│       └── search.py                    # Such-CLI (semantic/fulltext/hybrid/stats)
│
└── claudedocs/                           # Dokumentation
    ├── QUANTEC_PRO_Reverse_Engineering_Analyse.md
    ├── QUANTEC_Migration_Dokumentation.md
    ├── QUANTEC_Extraktionsplan_Graph_Vektor.md
    ├── QUANTEC_Phase2-4_Plan.md
    └── QUANTEC_Setup_und_Gebrauchsanweisung.md   # ← dieses Dokument
```

---

## 10. Haeufige Aufgaben

### Datenbank nach Neustart wiederherstellen

```bash
cd quantec_vector && docker compose up -d
```

Die Daten liegen im Docker-Volume `vecdata` und ueberleben Container-Neustarts.

### Datenbank komplett neu aufbauen

```bash
cd quantec_vector
docker compose down -v          # -v loescht das Volume!
docker compose up -d            # Erstellt leere DB mit Schema
sleep 3

# Daten aus Transferschicht kopieren
cd ../quantec_migration && docker compose up -d && cd ../quantec_vector
../quantec_migration/.venv/bin/python scripts/migrate_from_source.py

# Embeddings generieren (~10 Min)
../quantec_migration/.venv/bin/python scripts/generate_embeddings.py
```

### Embeddings fuer neue Eintraege nachberechnen

Das Script berechnet nur Embeddings fuer Items wo `embedding IS NULL`:

```bash
cd quantec_vector
../quantec_migration/.venv/bin/python scripts/generate_embeddings.py
```

### Einzelne SQL-Befehle ausfuehren

```bash
docker exec quantec_vector_db psql -U quantec -d quantec_vector -c "SELECT ..."
```

### Datenbank-Dump erstellen (Backup)

```bash
docker exec quantec_vector_db pg_dump -U quantec quantec_vector > backup_quantec_vector.sql
```

### Datenbank aus Dump wiederherstellen

```bash
docker exec -i quantec_vector_db psql -U quantec -d quantec_vector < backup_quantec_vector.sql
```

---

## 11. Technische Details

### Embedding-Modell

| Eigenschaft | Wert |
|-------------|------|
| Modell | paraphrase-multilingual-mpnet-base-v2 |
| Dimensionen | 768 |
| Sprachen | 50+ (DE, EN, Latein, etc.) |
| Groesse | ~420 MB |
| Normalisierung | L2-normalisiert (Cosine Distance) |
| Index | HNSW (m=16, ef_construction=200) |

### Distanz-Metrik

Die Suche verwendet **Cosine Distance** (`<=>` Operator in pgvector). Der angezeigte "Similarity"-Wert ist `(1 - distance) * 100`:
- **90-100%**: Sehr hohe Aehnlichkeit (fast identisch)
- **75-90%**: Hohe Aehnlichkeit (thematisch nah)
- **60-75%**: Moderate Aehnlichkeit (verwandt)
- **< 60%**: Schwache Aehnlichkeit

### XOR-Verschluesselungsschluessel (Original-DB)

```
Hex: bd ee ea c7 35 a5 64 6b 15 d8 3e 64 bb 89 df 93
```

Nur relevant fuer die Transferschicht und weitere Extraktion aus der `.store`-Datei.
