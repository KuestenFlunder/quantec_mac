-- Analyse-Views

-- Kategorie-Baum mit Pfad
CREATE VIEW v_category_tree AS
SELECT
    c.id,
    c.name,
    t.name AS theme,
    p.name AS parent_name,
    c.depth,
    c.item_count,
    c.path
FROM category c
LEFT JOIN theme t ON t.id = c.theme_id
LEFT JOIN category p ON p.id = c.parent_id
ORDER BY c.theme_id, c.path;

-- Themengebiet-Uebersicht
CREATE VIEW v_theme_overview AS
SELECT
    t.name AS theme,
    count(DISTINCT c.id) AS categories,
    sum(c.item_count) AS total_items,
    round(avg(e.quality_score)::numeric, 2) AS avg_quality
FROM theme t
JOIN category c ON c.theme_id = t.id
LEFT JOIN esoteric_item e ON e.category_id = c.id
GROUP BY t.id, t.name
ORDER BY total_items DESC;

-- Kategorie-Statistiken
CREATE VIEW v_category_stats AS
SELECT
    c.name AS category,
    t.name AS theme,
    c.item_count,
    round(avg(length(e.text_primary))::numeric, 1) AS avg_text_len,
    round(avg(e.quality_score)::numeric, 2) AS avg_quality,
    count(e.embedding) FILTER (WHERE e.embedding IS NOT NULL) AS embedded_count
FROM category c
LEFT JOIN theme t ON t.id = c.theme_id
LEFT JOIN esoteric_item e ON e.category_id = c.id
GROUP BY c.id, c.name, t.name, c.item_count
ORDER BY c.item_count DESC;

-- Beziehungsnetzwerk
CREATE VIEW v_category_network AS
SELECT
    cs.name AS source,
    ct.name AS target,
    cr.relation_type,
    cr.strength,
    array_length(cr.shared_keywords, 1) AS keyword_count,
    cr.shared_keywords
FROM category_relation cr
JOIN category cs ON cs.id = cr.source_category_id
JOIN category ct ON ct.id = cr.target_category_id
ORDER BY keyword_count DESC, cr.strength DESC;

-- Gesamtueberblick
CREATE VIEW v_overview AS
SELECT 'esoteric_item' AS tbl, count(*) AS rows FROM esoteric_item
UNION ALL SELECT 'category', count(*) FROM category
UNION ALL SELECT 'theme', count(*) FROM theme
UNION ALL SELECT 'category_relation', count(*) FROM category_relation
UNION ALL SELECT 'item_relation', count(*) FROM item_relation
UNION ALL SELECT 'mit_embedding', count(*) FROM esoteric_item WHERE embedding IS NOT NULL
ORDER BY rows DESC;
