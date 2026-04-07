# QUANTEC PRO -- Extraktionsplan: Baumstruktur, Graph- und Vektordatenbank

**Datum**: 2026-04-04
**Status**: Analyse abgeschlossen, Beziehungstabelle erstellt

---

## 1. Reverse Engineering der Baumstruktur

### 1.1 Entschluesselte BLOC-Payload-Struktur (0x5f52 Katalog-Records)

```
PAYLOAD EINES 0x5f52 RECORDS (nach 32-Byte BLOC-Header):

Offset  Bytes  Feld                  Beschreibung
------  -----  --------------------  ------------------------------------------
+0      4      OBJ_MAGIC             0xb8e1d508 (Objektklassen-Signatur)
+4      4      INSTANCE_HASH         3 Bytes variabel (Instanz-Identifikator)
+8      4      FIXED_CONST           0x00000029 (Festwert)
+12     20     SLOT_INDEX_A          5 x 4 Bytes: Feste Referenz-Tabelle
                                      (Modul-Slots: 0x002a-0x004f)
+32     16     SLOT_INDEX_B          4 x 4 Bytes: Variable Slot-Referenzen
                                      (Content-Pointer, variiert)
+48     4      CONTENT_PTR           Letzter Slot (b50-b51: Content-Pointer)
+52     4      CLASS_MARKER_1        0x125e0000 (Squeak/Smalltalk OOP)
+56     4      TYPE_SELF_REF         0x0001525f (Typ-Selbstreferenz: 0x5f52 + v1)
+60     4      CLASS_MARKER_2        0x125e0000
+64     4      MODULE_REF            0xff019060 (→ Modul 0x6090 "Psychosomatik")
+68     4      SENTINEL              0xffffffNN (Sentinel, NN variiert)
+72     4      VERSION_FLAG          0x00000100 (Version/Format-Flag)
+76     4      PARENT_NODE_ID        0x005e12XX (XX = Parent-Ordinal, 1 Byte!)
+80     4      DATA_TYPE_REF         0xYY000002 (YY = sub_ref → entity_type)
+84     4      CONTENT_HASH          Hash des Knoten-Inhalts
+88     1      TEXT_LENGTH           Laenge des folgenden Textes
+89     N      TEXT_CONTENT          UTF-8 Knoten-Label/Beschreibung
+89+N   pad    NULL_PADDING          Bis 16-Byte-Alignment
```

### 1.2 Parent-Child-Mechanismus

- **Knoten-Ordinal**: Header Byte 26 (High-Byte), Werte 0x00-0xFF
- **Parent-Pointer**: Payload Byte 79 (= 0x005e12**XX**), zeigt auf Parent-Ordinal
- **Problem**: Nur 256 moegliche Ordinal-Werte fuer 104.833 Records
- **Loesung**: Mehrere Records teilen sich ein Ordinal (Sub-Counter in Byte 26 Low-Byte)
  → Records mit gleichem Ordinal bilden einen **logischen Knoten**

**Baumtiefe**: 3-11 Ebenen, Median ca. 6

**3 Root-Knoten** (self-referenzierend):
- Ordinal 0x62: "Spiritual" (60 direkte Kinder)
- Ordinal 0xA0: "Spiritual/Aromatic Oils" (52 Kinder)
- Ordinal 0xBF: "Yellow Cone Flower - Self-knowledge" (22 Kinder)

### 1.3 Katalog → Daten-Verknuepfung

**sub_ref (Payload Byte 80)** verknuepft Katalog-Eintraege mit den eigentlichen Daten:

```
Katalog-Record (0x5f52)     →   Daten-Record (0xHH57)
  sub_ref = 0x60            →   type_base = 0x??60 (Bild-/Mediendaten)
  sub_ref = 0x57            →   type_base = 0x??57 (MorphicFieldItems)
  sub_ref = 0x56            →   type_base = 0x??56 (Alt. MorphicFieldItems)
```

### 1.4 OOP-Marker: Squeak/Smalltalk Herkunft

Die Konstante **0x125e** (4702 dez.) ist ein Squeak/Smalltalk Object-Oriented-Pointer. Die .store-Datei ist ein **serialisierter Smalltalk-Objektgraph**, kein relationales DB-Format. Das erklaert:
- Die Block-Struktur (Objekt-Serialisierung)
- Die Slot-Tabellen (Instanzvariablen)
- Das Ordinal-System (Object Identity)

---

## 2. Aktuelle Beziehungstabellen (implementiert)

### 2.1 category_relation (1.388 Beziehungen)

```sql
-- Schema
CREATE TABLE category_relation (
    source_category VARCHAR(200),
    target_category VARCHAR(200),
    relation_type VARCHAR(50),      -- 'shared_keyword'
    strength FLOAT,                 -- 0.0-1.0
    shared_keywords TEXT[],         -- z.B. {'Herz','Leber','Angst'}
    source VARCHAR(30)              -- 'keyword_analysis'
);

-- Statistik
-- 1.388 Beziehungen zwischen 196 Kategorien
-- Durchschnitt 2,3 gemeinsame Keywords pro Beziehung
-- Maximum 30 Keywords (Edelstein-Lexikon ↔ Edelsteine/Kristalle)
```

**Top-5 staerkste Verbindungen:**

| Kategorie A | Kategorie B | Keywords | Staerke |
|-------------|-------------|----------|---------|
| Edelstein-Lexikon | Edelsteine/Kristalle | 30 | 1.0 |
| Edelstein-Lexikon | Heilungs-Affirmationen | 28 | 0.95 |
| Heilungs-Affirmationen | ICD-10 Krankheiten | 27 | 1.0 |
| Edelstein-Lexikon | Homoeopathie Arzneimittelbilder | 27 | 1.0 |
| Edelsteine/Kristalle | Heilungs-Affirmationen | 27 | 0.92 |

**Hub-Kategorien** (meiste Verbindungen):
- Materia Medica (Detail) -- Verbindet 8/9 Keyword-Domaenen
- Radionik -- Verbindet 7/9 Keyword-Domaenen
- Edelstein-Lexikon -- 30 Bruecken-Keywords

### 2.2 item_relation (vorbereitet, noch leer)

```sql
-- Schema fuer Item-zu-Item Beziehungen
CREATE TABLE item_relation (
    source_item_id BIGINT,
    target_item_id BIGINT,
    relation_type VARCHAR(50),      -- 'behandelt', 'verweist_auf', 'verwandt_mit'
    confidence FLOAT,               -- 1.0 = manuell, <1.0 = automatisch
    source VARCHAR(30),             -- 'manual', 'text_extraction', 'embedding_similarity'
    metadata JSONB
);
```

---

## 3. Bewertung: Graph- vs. Vektor-Datenbank

### 3.1 Vergleichsmatrix

| Kriterium | Neo4j (Graph) | Vektor-DB | PG + pgvector (Hybrid) | RDF/SPARQL |
|-----------|:---:|:---:|:---:|:---:|
| Migrationsaufwand | Hoch | Mittel | **Niedrig** | Sehr hoch |
| Strukturierte Abfragen | Gut | Schwach | **Stark** | Gut |
| Semantische Suche | Schwach | **Stark** | Stark | Schwach |
| Graph-Traversierung | **Stark** | -- | Maessig | Stark |
| Mac-App-Integration | Maessig | Gut | **Hervorragend** | Schlecht |
| Wartungsaufwand | Mittel-Hoch | Mittel | **Niedrig** | Hoch |
| Time-to-Value | Wochen | Tage | **Stunden** | Monate |

### 3.2 Empfehlung: PostgreSQL + pgvector + Beziehungstabellen

**Begruendung:**
1. **Daten sind bereits in PostgreSQL** -- kein Technologiewechsel noetig
2. **Beziehungen muessen erst aufgebaut werden** -- das ist unabhaengig von der DB-Technologie die eigentliche Arbeit
3. **Semantische Suche + strukturierte Filter in einem Query** -- der entscheidende Vorteil
4. **Mac-App-Pfad klar** -- PostgreSQL + Swift/Electron ohne zusaetzliche Infrastruktur
5. **117K Records = kein Scale-Problem** -- Neo4j/RDF loesen Probleme die hier nicht existieren

### 3.3 Empfohlene Erweiterungen

```sql
-- 1. pgvector fuer Embeddings
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE morphic_field_item ADD COLUMN embedding vector(768);
CREATE INDEX idx_mfi_embedding ON morphic_field_item 
    USING hnsw (embedding vector_cosine_ops);

-- 2. Embedding-Modell: multilingual-e5-large (Microsoft)
--    Gruende: DE+EN+Latein, 1024 Dim, offline-faehig
--    Anreicherung: "Abies nigra" → "Abies nigra -- Homoeopathie, Nadelbaum, Magen"
```

---

## 4. Datenqualitaet und Bereinigungsbedarf

### 4.1 Artefakte

| Problem | Betroffene Records | Anteil |
|---------|-------------------|--------|
| Binaer-Artefakte in text_primary | 28.050 | 24,0% |
| NULL text_primary | 7.457 | 6,4% |
| Kurztexte (1-10 Zeichen) | 10.134 | 8,7% |
| **Sauber** | **71.389** | **61,0%** |

### 4.2 Bereinigungsstrategie (priorisiert)

1. **Prio 1**: Binaer-Praefixe entfernen (`"K |`, Hex-Fragmente)
2. **Prio 2**: NULL text_primary aus text_full befuellen (7.457 Records)
3. **Prio 3**: Text-Anreicherung fuer Embeddings (Kontext zu Kurzbegriffen)
4. **Prio 4**: Pipe-Delimiter `|` in text_full als semantische Trenner beibehalten

### 4.3 Textlaengen-Verteilung

| Bereich | Records | Anteil |
|---------|---------|--------|
| NULL | 7.457 | 6,4% |
| 1-10 Zeichen | 10.134 | 8,7% |
| 11-30 Zeichen | 37.804 | 32,3% |
| 31-100 Zeichen | 44.626 | 38,1% |
| 101-300 Zeichen | 15.955 | 13,6% |
| 300+ Zeichen | 1.054 | 0,9% |

---

## 5. Extraktionsplan (Phasen)

### Phase 1: Textbereinigung (sofort machbar)
- Binaer-Artefakte per Regex bereinigen
- NULL text_primary aus text_full ableiten
- Qualitaets-Score pro Record berechnen

### Phase 2: Baumstruktur extrahieren (aufwaendig)
- BLOC-Parser erweitern: Parent-Ordinal (Byte 26) und Parent-Pointer (Byte 79) extrahieren
- Ordinal → Logische Knoten gruppieren
- Baum rekonstruieren (3 Roots → Ebenen → Blaetter)
- In `morphic_field_category` als Hierarchie abbilden (parent_id, depth, path)

### Phase 3: Item-Beziehungen aufbauen
- Textuelle Kreuzreferenzen: "Nosode" in Homoeopathie → Link zu Nosoden-Kategorie
- ICD-10 Code-Erkennung in Materia-Medica-Texten
- Organ-basierte Verknuepfungen (Herz verbindet 144 Kategorien)
- In `item_relation` als (source, target, type, confidence) speichern

### Phase 4: Vektordatenbank (optional)
- pgvector Extension aktivieren
- Embeddings mit multilingual-e5-large berechnen (117K Records, ~2-4 Std)
- HNSW-Index fuer semantische Suche
- Hybrid-Queries: SQL-Filter + Vektor-Naehe

---

## 6. Verbindung zur Mac-App

### Empfohlener Stack
- **Backend**: PostgreSQL (Docker oder Postgres.app)
- **Suche**: pgvector (semantisch) + GIN (Volltext) + SQL (strukturiert)
- **Beziehungen**: category_relation + item_relation Tabellen
- **Frontend**: Electron (Cross-Platform) oder Swift/SwiftUI (native Mac)
- **Kommunikation**: PostgresNIO (Swift) oder pg-promise (Node.js/Electron)

### Query-Beispiele

```sql
-- "Welche Mittel helfen bei Angst?" (strukturiert + semantisch)
SELECT m.category_name, m.text_primary, m.embedding <-> query_vec AS distance
FROM morphic_field_item m
WHERE m.category_name IN ('Homoeopathie Arzneimittel', 'Bach-Blueten Einzelmittel', 
                           'Edelsteine/Kristalle', 'Heilungs-Affirmationen')
ORDER BY m.embedding <-> query_vec
LIMIT 20;

-- "Welche Kategorien sind mit Edelsteinen verwandt?" (Graph-Traversierung)
SELECT target_category, strength, shared_keywords
FROM category_relation
WHERE source_category = 'Edelsteine/Kristalle'
ORDER BY array_length(shared_keywords, 1) DESC;

-- "Finde alles was mit dem Herz zusammenhaengt" (Cross-Kategorie)
SELECT category_name, count(*) as treffer
FROM morphic_field_item
WHERE text_full ILIKE '%herz%'
GROUP BY category_name
ORDER BY treffer DESC;
```
