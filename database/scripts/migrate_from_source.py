"""Migriert bereinigte Daten von quantec_db (Migrationsschicht) nach quantec_vector_db."""
import psycopg
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).parent.parent / ".env")

SOURCE = os.getenv("SOURCE_DB", "postgresql://quantec:quantec_dev_2026@localhost:5433/quantec")
TARGET = os.getenv("TARGET_DB", "postgresql://quantec:quantec_vec_2026@localhost:5434/quantec_vector")

# Themengebiet-Zuordnung (aus unserer Analyse)
THEME_MAP = {
    "Nosoden & Infektiologie": ["nosod", "virus", "parasit", "bakterio", "mykolog", "egel", "nematod",
        "candidose", "infekt", "rheuma", "haemato", "lebensmittelzus", "umweltgift", "kunststoff",
        "material-", "strahlung", "chemie-", "perioden", "element-", "craniosacr"],
    "Homoeopathie & Praeparate": ["homoeo", "injeel", "oligoplex", "spagyrik", "konstitution",
        "materia medica", "horvi", "heel", "quebracho", "einzelmittel", "rezeptur", "sanum",
        "synergon", "ceres", "anthropos", "cyl-praep"],
    "Medizin & Genetik": ["icd-10", "chromosom", "genetik", "omim", "biochem", "molekuel",
        "bioinformatik", "syndrom"],
    "Phytotherapie & Pflanzen": ["phyto", "kraeut", "pflanz", "gemmoth", "dendro", "wildkr",
        "gift", "baum-aff", "obst", "frucht", "tee-rezept", "beerenfr"],
    "TCM & Akupunktur": ["akupunkt", "tcm", "meridi", "5-element", "funktionskreis",
        "leber-therap", "organbezueg", "feng shui", "i-ging"],
    "Edelsteine & Kristalle": ["edelstein", "kristall", "mineral", "opal"],
    "Affirmationen & Weisheiten": ["affirmation", "weisheit", "zitat", "tugend", "werte",
        "sprichw", "glueck", "ruhe-", "ich-bin", "lebensweisheit", "veraenderung"],
    "Tarot & Archetypen": ["tarot", "arkan", "archetyp", "karten"],
    "Religion & Spiritualitaet": ["koran", "bibel", "islam", "sufism", "engel", "schutzengel",
        "kabbala", "mantra", "gebet", "christl", "heilige namen", "aufgestieg", "sephiroth",
        "lichtstrahl"],
    "Chakren & Energiearbeit": ["chakra", "aura-therap", "aura-soma", "energie-aff", "jin shin",
        "urmeridian", "kundalini"],
    "Bluetentherapie": ["bach-bluet", "bluetenessenzen", "kaliforn", "tropisch", "wuesten",
        "maya-heil", "essenz"],
    "Aromatherapie": ["aetherisch", "aroma"],
    "Anatomie & Physiologie": ["anatom", "organ", "hirn", "neuro", "wirbel", "zellbio",
        "myelin", "reflex", "gelenk", "zahn", "hormon", "augen", "progest"],
    "Nahrungsergaenzung & Pharma": ["nahrung", "vitamin", "amino", "supplement", "anti-aging",
        "vital", "probiot", "biotics", "chronobio", "pharma", "praeparat", "indikation",
        "leberthera", "antimykot", "nerven", "apothek", "schuessler"],
    "Symbole & Kraftplaetze": ["kraft", "symbol", "kornkreis", "wallfahrt", "tempel",
        "kraftplae", "maya-kal", "schaman", "geometrie", "platon", "mandala", "runen"],
    "Spirituelle Kurse": ["lektion", "acim", "kurs"],
    "Klang & Frequenzen": ["klang", "frequenz", "oktav", "musik", "komposition"],
    "Psychologie & Therapie": ["psycho", "famili", "genogramm", "aufstellung",
        "therapie-method", "radionik", "bwl"],
    "Geobiologie & Geopathie": ["geopath", "geobio", "erdstrahl", "gitter", "boden",
        "feinstoff", "raum-energ"],
    "Farbtherapie": ["farb", "aura-soma farb", "lichtstrahl-therap"],
    "Astrologie & Numerologie": ["numerolog", "astrolog", "haeuser"],
    "Tierheilkunde": ["tierheil", "veterin"],
    "Enzymklassifikation": ["enzym"],
    "Sonstige": [],
}


def classify_theme(category_name: str) -> str:
    name_lower = category_name.lower()
    for theme, keywords in THEME_MAP.items():
        if theme == "Sonstige":
            continue
        for kw in keywords:
            if kw in name_lower:
                return theme
    return "Sonstige"


def compute_quality(text_primary, text_full) -> float:
    if not text_primary:
        return 0.0
    score = 0.0
    # Laenge (laengerer Text = besser, bis 200 Zeichen)
    score += min(len(text_primary) / 200.0, 0.4)
    # Beginnt mit Buchstabe
    if text_primary[0].isalpha():
        score += 0.2
    # Kein Artefakt
    if all(ord(c) >= 32 for c in text_primary):
        score += 0.2
    # text_full hat mehr Info
    if text_full and len(text_full) > len(text_primary) + 10:
        score += 0.2
    return min(score, 1.0)


def migrate():
    src = psycopg.connect(SOURCE)
    tgt = psycopg.connect(TARGET)

    # --- Themes ---
    print("Migriere Themes...")
    themes = {}
    with tgt.cursor() as cur:
        for i, name in enumerate(sorted(THEME_MAP.keys())):
            cur.execute("INSERT INTO theme (name, sort_order) VALUES (%s, %s) RETURNING id", (name, i))
            themes[name] = cur.fetchone()[0]
    tgt.commit()
    print(f"  {len(themes)} Themes angelegt")

    # --- Categories ---
    print("Migriere Kategorien...")
    with src.cursor() as cur:
        cur.execute("""
            SELECT category_name, count(*) as cnt
            FROM morphic_field_item
            GROUP BY category_name
            ORDER BY cnt DESC
        """)
        src_categories = cur.fetchall()

    cat_map = {}  # name → new_id
    with tgt.cursor() as cur:
        for name, cnt in src_categories:
            theme_name = classify_theme(name)
            theme_id = themes.get(theme_name, themes["Sonstige"])
            cur.execute(
                "INSERT INTO category (name, theme_id, item_count) VALUES (%s, %s, %s) RETURNING id",
                (name, theme_id, cnt),
            )
            cat_map[name] = cur.fetchone()[0]
    tgt.commit()
    print(f"  {len(cat_map)} Kategorien angelegt")

    # --- Esoteric Items ---
    print("Migriere 117K Items...")
    batch = []
    batch_size = 2000
    total = 0

    with src.cursor("src_cursor") as cur:
        cur.execute("""
            SELECT category_name, text_primary, text_secondary, text_full, extra
            FROM morphic_field_item
            ORDER BY id
        """)

        for row in cur:
            cat_name, tp, ts, tf, extra = row
            cat_id = cat_map.get(cat_name)
            if not cat_id:
                continue

            qs = compute_quality(tp, tf)
            batch.append((cat_id, cat_name, tp, ts, tf, qs, extra))

            if len(batch) >= batch_size:
                _flush_items(tgt, batch)
                total += len(batch)
                batch.clear()
                if total % 20000 == 0:
                    print(f"  {total:,} Items...")

    if batch:
        _flush_items(tgt, batch)
        total += len(batch)
    tgt.commit()
    print(f"  {total:,} Items migriert")

    # --- Category Relations ---
    print("Migriere Beziehungen...")
    rel_count = 0
    with src.cursor() as scur:
        scur.execute("SELECT source_category, target_category, relation_type, strength, shared_keywords FROM category_relation")
        with tgt.cursor() as tcur:
            for src_cat, tgt_cat, rtype, strength, kws in scur:
                src_id = cat_map.get(src_cat)
                tgt_id = cat_map.get(tgt_cat)
                if src_id and tgt_id:
                    tcur.execute(
                        "INSERT INTO category_relation (source_category_id, target_category_id, relation_type, strength, shared_keywords) "
                        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (src_id, tgt_id, rtype, strength, kws),
                    )
                    rel_count += 1
    tgt.commit()
    print(f"  {rel_count} Beziehungen migriert")

    # --- Import Log ---
    with tgt.cursor() as cur:
        cur.execute(
            "INSERT INTO import_log (source_db, item_count, category_count, relation_count, notes) "
            "VALUES (%s, %s, %s, %s, %s)",
            (SOURCE, total, len(cat_map), rel_count, "Initiale Migration aus Transferschicht"),
        )
    tgt.commit()

    src.close()
    tgt.close()
    print(f"\n=== Migration abgeschlossen ===")
    print(f"  Items: {total:,}")
    print(f"  Kategorien: {len(cat_map)}")
    print(f"  Themes: {len(themes)}")
    print(f"  Beziehungen: {rel_count}")


def _flush_items(conn, batch):
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO esoteric_item (category_id, category_name, text_primary, text_secondary, text_full, quality_score, extra) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            batch,
        )
    conn.commit()


if __name__ == "__main__":
    migrate()
