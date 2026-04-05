-- QUANTEC Vektor-Datenbank: Sauberes Produktionsschema
-- pgvector Extension aktivieren

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Themengebiete (Top-Level Gruppierung)
-- ============================================================

CREATE TABLE theme (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    sort_order INTEGER DEFAULT 0
);

-- ============================================================
-- Kategorien mit Hierarchie
-- ============================================================

CREATE TABLE category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    theme_id INTEGER REFERENCES theme(id),
    parent_id INTEGER REFERENCES category(id),
    depth INTEGER DEFAULT 0,
    path INTEGER[],
    item_count INTEGER DEFAULT 0,
    description TEXT
);

-- ============================================================
-- Esoterische Haupttabelle (bereinigt, ohne Legacy)
-- ============================================================

CREATE TABLE esoteric_item (
    id BIGSERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES category(id),
    category_name VARCHAR(200) NOT NULL,
    text_primary TEXT,
    text_secondary TEXT,
    text_full TEXT,
    quality_score REAL DEFAULT 0.0,
    embedding vector(768),
    extra JSONB
);

-- ============================================================
-- Kategorie-zu-Kategorie Beziehungen
-- ============================================================

CREATE TABLE category_relation (
    id SERIAL PRIMARY KEY,
    source_category_id INTEGER NOT NULL REFERENCES category(id),
    target_category_id INTEGER NOT NULL REFERENCES category(id),
    relation_type VARCHAR(50) NOT NULL,
    strength REAL DEFAULT 0.0,
    shared_keywords TEXT[],
    UNIQUE(source_category_id, target_category_id, relation_type)
);

-- ============================================================
-- Item-zu-Item Beziehungen (Phase 3+)
-- ============================================================

CREATE TABLE item_relation (
    id BIGSERIAL PRIMARY KEY,
    source_item_id BIGINT NOT NULL REFERENCES esoteric_item(id),
    target_item_id BIGINT NOT NULL REFERENCES esoteric_item(id),
    relation_type VARCHAR(50) NOT NULL,
    confidence REAL DEFAULT 1.0,
    source VARCHAR(30) NOT NULL,
    metadata JSONB,
    UNIQUE(source_item_id, target_item_id, relation_type)
);

-- ============================================================
-- Import-Metadaten
-- ============================================================

CREATE TABLE import_log (
    id SERIAL PRIMARY KEY,
    source_db VARCHAR(100),
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    item_count INTEGER,
    category_count INTEGER,
    relation_count INTEGER,
    notes TEXT
);
