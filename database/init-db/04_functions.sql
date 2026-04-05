-- Such-Funktionen fuer die Vektor-Datenbank

-- Kategorie-Nachbarn (ueber shared keywords)
CREATE OR REPLACE FUNCTION category_neighbors(cat_id INTEGER, n INTEGER DEFAULT 10)
RETURNS TABLE(
    neighbor_id INTEGER,
    neighbor_name VARCHAR,
    relation_type VARCHAR,
    strength REAL,
    keyword_count INTEGER,
    shared_keywords TEXT[]
) AS $$
    SELECT
        ct.id,
        ct.name,
        cr.relation_type,
        cr.strength,
        array_length(cr.shared_keywords, 1),
        cr.shared_keywords
    FROM category_relation cr
    JOIN category ct ON ct.id = CASE
        WHEN cr.source_category_id = cat_id THEN cr.target_category_id
        ELSE cr.source_category_id
    END
    WHERE cr.source_category_id = cat_id OR cr.target_category_id = cat_id
    ORDER BY array_length(cr.shared_keywords, 1) DESC, cr.strength DESC
    LIMIT n;
$$ LANGUAGE sql STABLE;

-- Volltext-Suche (GIN-basiert, kein Embedding noetig)
CREATE OR REPLACE FUNCTION fulltext_search(query TEXT, n INTEGER DEFAULT 20)
RETURNS TABLE(
    id BIGINT,
    category_name VARCHAR,
    text_primary TEXT,
    rank REAL
) AS $$
    SELECT
        e.id,
        e.category_name,
        e.text_primary,
        ts_rank(
            to_tsvector('german', coalesce(e.text_primary,'') || ' ' || coalesce(e.text_full,'')),
            plainto_tsquery('german', query)
        ) AS rank
    FROM esoteric_item e
    WHERE to_tsvector('german', coalesce(e.text_primary,'') || ' ' || coalesce(e.text_full,''))
          @@ plainto_tsquery('german', query)
    ORDER BY rank DESC
    LIMIT n;
$$ LANGUAGE sql STABLE;

-- Erweiterte Views fuer Phase 4

-- Qualitaets-Verteilung
CREATE OR REPLACE VIEW v_quality_distribution AS
SELECT
    CASE
        WHEN quality_score >= 0.8 THEN 'A: Sehr gut (0.8+)'
        WHEN quality_score >= 0.6 THEN 'B: Gut (0.6-0.8)'
        WHEN quality_score >= 0.4 THEN 'C: Mittel (0.4-0.6)'
        WHEN quality_score >= 0.2 THEN 'D: Schwach (0.2-0.4)'
        ELSE 'E: Minimal (0-0.2)'
    END AS quality_band,
    count(*) AS items,
    round(count(*)::numeric / (SELECT count(*) FROM esoteric_item) * 100, 1) AS pct
FROM esoteric_item
GROUP BY 1
ORDER BY 1;

-- Embedding-Abdeckung pro Kategorie
CREATE OR REPLACE VIEW v_embedding_coverage AS
SELECT
    c.name AS category,
    t.name AS theme,
    c.item_count AS total,
    count(e.embedding) AS embedded,
    round(count(e.embedding)::numeric / GREATEST(c.item_count, 1) * 100, 1) AS coverage_pct
FROM category c
LEFT JOIN theme t ON t.id = c.theme_id
LEFT JOIN esoteric_item e ON e.category_id = c.id AND e.embedding IS NOT NULL
GROUP BY c.id, c.name, t.name, c.item_count
ORDER BY c.item_count DESC;
