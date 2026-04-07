# QUANTEC Vektor-DB: Detailplan Phase 2-4

**Datum**: 2026-04-04
**Abhaengigkeit**: Phase 1 abgeschlossen -- quantec_vector_db laeuft auf Port 5434

---

## Aktueller Stand (Phase 1 erledigt)

```
quantec_vector_db (Port 5434, pgvector/pgvector:pg16)
├── pgvector 0.8.2 aktiv
├── theme:             24 Themengebiete
├── category:          256 Kategorien
├── esoteric_item:     117.030 bereinigte Eintraege
├── category_relation: 1.388 Beziehungen
├── item_relation:     0 (leer, fuer Phase 3)
├── embedding:         0 (NULL, fuer Phase 3)
└── Views: v_overview, v_theme_overview, v_category_stats, v_category_tree, v_category_network
```

**Verbindungsdaten:**
```
Host: localhost:5434
DB:   quantec_vector
User: quantec
PW:   quantec_vec_2026
```

---

## Phase 2: Baumstruktur extrahieren

### Ziel
Die 256 Kategorien in eine hierarchische Baumstruktur bringen (parent_id, depth, path). Die Hierarchie steckt in den 0x5f52 Katalog-Records der Original-`.store`-Datei.

### 2.1 Parser: Parent-Child aus .store extrahieren

**Script**: `quantec_vector/scripts/extract_tree.py`

**Algorithmus:**
1. Scanne alle 104.833 Records vom Typ 0x5f52 in der .store-Datei
2. Pro Record extrahiere:
   - **node_ordinal** = Header Byte 26 (High-Byte), 0x00-0xFF
   - **parent_ordinal** = Payload Byte 79 (aus dem Pattern `0x005e12XX`), 0x00-0xFF
   - **sub_ref** = Payload Byte 80 (verweist auf entity_type der Daten-Records)
   - **text** = UTF-8 nach `?!` Marker (wenn vorhanden)
3. Gruppiere Records nach node_ordinal → logische Knoten
4. Baue Baum: parent_ordinal → node_ordinal Kanten

**Herausforderung**: 256 moegliche Ordinalwerte fuer 104.833 Records. Mehrere Records teilen ein Ordinal. Die Text-Labels kommen aus den ~2.228 Records die Text enthalten.

**Mapping auf Kategorien**: 
- Die sub_ref Werte (0x57, 0x56, etc.) mit dem category_id der type_base Werte korrelieren
- Z.B. Knoten mit sub_ref=0x57 und Text "Homoeopathie" → category "Homoeopathie Arzneimittel"

### 2.2 In category-Tabelle abbilden

```sql
-- Felder die befuellt werden:
UPDATE category SET 
    parent_id = <ermittelter Parent>,
    depth = <Tiefe im Baum>,
    path = <Array der Vorfahren-IDs>
WHERE id = <category_id>;
```

**Erwartetes Ergebnis:**
- 3 Root-Knoten (Ordinal 0x62, 0xA0, 0xBF)
- 20-50 Zwischenknoten (werden als neue Kategorien ohne Items angelegt)
- 256 Blatt-Knoten = bestehende Kategorien
- Tiefe: 3-11 Ebenen

### 2.3 Fallback falls Binaer-Parsing zu fragil

Falls die Ordinal-Extraktion nicht zuverlaessig genug ist:
- **Alternative A**: Manuelle Zuordnung der 256 Kategorien unter die 24 Themes (flacher 2-Ebenen-Baum)
- **Alternative B**: Semantische Clusterung via Embeddings (Phase 3) als automatische Hierarchie

### 2.4 Verifikation

```sql
-- Alle Kategorien haben einen Parent (ausser Roots)
SELECT count(*) FROM category WHERE parent_id IS NULL; -- = 3 (Roots) oder 24 (Themes)

-- Baum ist konsistent (keine Zyklen)
WITH RECURSIVE tree AS (
    SELECT id, parent_id, 1 as depth FROM category WHERE parent_id IS NULL
    UNION ALL
    SELECT c.id, c.parent_id, t.depth + 1 FROM category c JOIN tree t ON c.parent_id = t.id
)
SELECT max(depth) as max_depth, count(*) as reachable FROM tree;
-- reachable = 256 + Zwischenknoten, max_depth = 3-11
```

---

## Phase 3: Vektorisierung mit pgvector

### Ziel
Jeder der 117.030 esoteric_items bekommt ein 768-dimensionales Embedding fuer semantische Suche.

### 3.1 Technische Vorbereitung

**Dependencies installieren:**
```bash
pip install sentence-transformers torch
```

**Modell**: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- 768 Dimensionen
- Unterstuetzt DE, EN, Latein, ~50 Sprachen
- ~420 MB Modell-Download
- Offline-faehig (kein API-Key noetig)
- Performance: ~500-1000 Saetze/Sekunde auf M1/M2 Mac (MPS)

### 3.2 Text-Anreicherung (vor dem Embedding)

Kurze Begriffe ohne Kontext ergeben schwache Embeddings. Strategie:

```python
def enrich_text(text_primary, text_full, category_name):
    """Erzeugt angereicherten Text fuer das Embedding."""
    # Verwende text_full wenn deutlich laenger
    base = text_full if text_full and len(text_full) > len(text_primary or '') + 20 else (text_primary or '')
    
    # Kategorie als Kontext voranstellen bei Kurztexten
    if len(base) < 30:
        return f"{category_name}: {base}"
    return base
```

**Beispiele:**
| Original | Angereichert |
|----------|-------------|
| "Abies nigra" | "Homoeopathie Arzneimittel: Abies nigra" |
| "Achat" | "Edelsteine/Kristalle: Achat" |
| "001. Sura zur Eroeffnung..." (lang) | "001. Sura zur Eroeffnung..." (unveraendert) |

### 3.3 Embedding-Pipeline

**Script**: `quantec_vector/scripts/generate_embeddings.py`

```python
# Pseudocode
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

# Batch-Lesen aus DB
for batch in read_batches(esoteric_item, size=64):
    texts = [enrich_text(r.text_primary, r.text_full, r.category_name) for r in batch]
    embeddings = model.encode(texts, normalize_embeddings=True)
    update_embeddings(batch.ids, embeddings)  # UPDATE esoteric_item SET embedding = %s WHERE id = %s

# HNSW-Index NACH dem Import erstellen (schneller)
CREATE INDEX idx_ei_embedding ON esoteric_item 
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200);
```

**Geschaetzte Laufzeit:**
- 117.030 Records / 64 Batch-Size = ~1.829 Batches
- ~500 Saetze/Sek auf Apple Silicon → **~4 Minuten** fuer Embeddings
- HNSW-Index-Erstellung: ~1-2 Minuten
- **Gesamt: ~6-8 Minuten**

### 3.4 Verifikation

```sql
-- Alle Items haben Embeddings
SELECT count(*) FROM esoteric_item WHERE embedding IS NOT NULL;  -- = 117.030

-- Embedding-Dimensionalitaet
SELECT vector_dims(embedding) FROM esoteric_item LIMIT 1;  -- = 768

-- Schnelltest: Semantische Naehe
SELECT category_name, text_primary, 
       embedding <=> (SELECT embedding FROM esoteric_item WHERE text_primary = 'Angst' LIMIT 1) as distance
FROM esoteric_item
WHERE embedding IS NOT NULL
ORDER BY distance
LIMIT 10;
```

---

## Phase 4: Analyse-Views + Semantic Search Funktionen

### 4.1 SQL-Funktionen (in `04_functions.sql`)

**semantic_search(query_text, limit)**
```sql
CREATE FUNCTION semantic_search(query_embedding vector(768), n INTEGER DEFAULT 10)
RETURNS TABLE(id BIGINT, category_name VARCHAR, text_primary TEXT, distance FLOAT) AS $$
    SELECT id, category_name, text_primary, 
           embedding <=> query_embedding as distance
    FROM esoteric_item
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding
    LIMIT n;
$$ LANGUAGE sql STABLE;
```

**Hinweis**: Das Query-Embedding muss in Python erzeugt und als Parameter uebergeben werden. Eine reine SQL-Funktion kann kein Embedding berechnen. Fuer eine Mac-App wuerde ein Python-Microservice oder eine eingebettete Embedding-Berechnung benoetigt.

**hybrid_search(query_embedding, category_filter, limit)**
```sql
-- Kombination: Vektor-Naehe + Kategorie-Filter
SELECT id, category_name, text_primary, embedding <=> query_embedding as distance
FROM esoteric_item
WHERE category_name = ANY(category_filter)
AND embedding IS NOT NULL
ORDER BY embedding <=> query_embedding
LIMIT n;
```

**category_neighbors(category_id)**
```sql
SELECT ct.name, cr.strength, cr.shared_keywords
FROM category_relation cr
JOIN category ct ON ct.id = cr.target_category_id
WHERE cr.source_category_id = category_id
ORDER BY array_length(cr.shared_keywords, 1) DESC;
```

### 4.2 Python-Search-Client

**Script**: `quantec_vector/scripts/search.py`

```python
# CLI fuer semantische Suche
# Laedt das Embedding-Modell und erzeugt Query-Vektoren
# Fuehrt dann die SQL-Funktion aus

def search(query: str, category: str = None, limit: int = 10):
    embedding = model.encode(query, normalize_embeddings=True)
    # ... SQL ausfuehren mit embedding als Parameter
```

### 4.3 Erweiterte Views

**v_quality_distribution**: Verteilung der Qualitaets-Scores
**v_embedding_coverage**: Anteil der Items mit Embedding pro Kategorie
**v_similar_categories**: Top-5 aehnlichste Kategorien basierend auf durchschnittlicher Embedding-Naehe

---

## Zeitschaetzung

| Phase | Aufwand | Abhaengigkeit |
|-------|---------|---------------|
| Phase 2: Baumstruktur | 2-4 Stunden (Binaer-Parsing + Verifikation) | .store-Datei |
| Phase 3: Vektorisierung | ~30 Min (Script + ~8 Min Laufzeit) | sentence-transformers installiert |
| Phase 4: Views + Search | ~1 Stunde | Phase 3 abgeschlossen |

**Phase 3 kann unabhaengig von Phase 2 ausgefuehrt werden.** Empfohlene Reihenfolge: 3 → 4 → 2 (Embeddings zuerst, Baumstruktur spaeter).

---

## Dateien-Uebersicht

```
quantec_vector/
  docker-compose.yml              ✅ erstellt (Port 5434)
  .env                            ✅ erstellt
  init-db/
    01_schema.sql                  ✅ erstellt (pgvector + 6 Tabellen)
    02_indexes.sql                 ✅ erstellt (HNSW auskommentiert)
    03_views.sql                   ✅ erstellt (5 Views)
    04_functions.sql               📋 Phase 4
  scripts/
    migrate_from_source.py         ✅ erstellt + ausgefuehrt
    extract_tree.py                📋 Phase 2
    generate_embeddings.py         📋 Phase 3
    search.py                      📋 Phase 4
```

---

## Naechster Schritt

**Empfehlung**: Phase 3 (Vektorisierung) zuerst, da sie unabhaengig ist und sofort semantische Suche ermoeglicht. Phase 2 (Baumstruktur) erfordert weiteres Binaer-Reverse-Engineering und kann parallel oder spaeter erfolgen.
