-- Indizes fuer die Vektor-Datenbank

-- category
CREATE INDEX idx_cat_theme ON category(theme_id);
CREATE INDEX idx_cat_parent ON category(parent_id);
CREATE INDEX idx_cat_path ON category USING gin(path);

-- esoteric_item: Standard-Indizes
CREATE INDEX idx_ei_category ON esoteric_item(category_id);
CREATE INDEX idx_ei_category_name ON esoteric_item(category_name);
CREATE INDEX idx_ei_quality ON esoteric_item(quality_score);
CREATE INDEX idx_ei_text_primary ON esoteric_item(text_primary) WHERE text_primary IS NOT NULL;

-- esoteric_item: Full-Text-Search (GIN)
CREATE INDEX idx_ei_fulltext ON esoteric_item
    USING gin(to_tsvector('german', coalesce(text_primary,'') || ' ' || coalesce(text_full,'')));

-- esoteric_item: pgvector HNSW Index (wird nach Embedding-Import erstellt)
-- CREATE INDEX idx_ei_embedding ON esoteric_item
--     USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200);

-- category_relation
CREATE INDEX idx_cr_source ON category_relation(source_category_id);
CREATE INDEX idx_cr_target ON category_relation(target_category_id);
CREATE INDEX idx_cr_type ON category_relation(relation_type);

-- item_relation
CREATE INDEX idx_ir_source ON item_relation(source_item_id);
CREATE INDEX idx_ir_target ON item_relation(target_item_id);
CREATE INDEX idx_ir_type ON item_relation(relation_type);
