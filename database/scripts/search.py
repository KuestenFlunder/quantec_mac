"""Semantische Suche ueber die QUANTEC Vektor-Datenbank."""
import os
import sys
import click
import psycopg
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
TARGET_DB = os.getenv("TARGET_DB", "postgresql://quantec:quantec_vec_2026@localhost:5434/quantec_vector")

_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    return _model


def embed_query(text: str) -> list[float]:
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


@click.group()
def cli():
    """QUANTEC Vektor-Suche."""
    pass


@cli.command()
@click.argument("query")
@click.option("-n", "--limit", default=15, help="Anzahl Ergebnisse")
@click.option("-c", "--category", default=None, help="Kategorie-Filter")
@click.option("-t", "--theme", default=None, help="Themengebiet-Filter")
def semantic(query, limit, category, theme):
    """Semantische Suche (Vektor-Aehnlichkeit)."""
    click.echo(f"Suche: \"{query}\" ...")
    emb = embed_query(query)

    conn = psycopg.connect(TARGET_DB)
    with conn.cursor() as cur:
        sql = """
            SELECT e.category_name, e.text_primary,
                   round((1 - (e.embedding <=> %s::vector))::numeric * 100, 1) as similarity_pct
            FROM esoteric_item e
            WHERE e.embedding IS NOT NULL
        """
        params = [emb]

        if category:
            sql += " AND e.category_name ILIKE %s"
            params.append(f"%{category}%")
        if theme:
            sql += " AND e.category_id IN (SELECT id FROM category WHERE theme_id IN (SELECT id FROM theme WHERE name ILIKE %s))"
            params.append(f"%{theme}%")

        sql += " ORDER BY e.embedding <=> %s::vector LIMIT %s"
        params.extend([emb, limit])

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    click.echo(f"\n{'Kategorie':<35} {'Similarity':>10}  Text")
    click.echo("-" * 100)
    for cat, text, sim in results:
        text_short = (text or "")[:60]
        click.echo(f"{cat:<35} {sim:>8}%  {text_short}")


@cli.command()
@click.argument("query")
@click.option("-n", "--limit", default=15)
def fulltext(query, limit):
    """Volltext-Suche (GIN-basiert, kein Embedding)."""
    conn = psycopg.connect(TARGET_DB)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM fulltext_search(%s, %s)", (query, limit))
        results = cur.fetchall()
    conn.close()

    click.echo(f"\n{'Kategorie':<35} {'Rank':>6}  Text")
    click.echo("-" * 100)
    for id, cat, text, rank in results:
        click.echo(f"{cat:<35} {rank:>6.3f}  {(text or '')[:60]}")


@cli.command()
@click.argument("query")
@click.option("-n", "--limit", default=15)
@click.option("-c", "--category", default=None)
def hybrid(query, limit, category):
    """Hybrid-Suche: Volltext-Vorfilter + Vektor-Ranking."""
    click.echo(f"Hybrid-Suche: \"{query}\" ...")
    emb = embed_query(query)

    conn = psycopg.connect(TARGET_DB)
    with conn.cursor() as cur:
        sql = """
            WITH candidates AS (
                SELECT id, category_name, text_primary, text_full
                FROM esoteric_item
                WHERE to_tsvector('german', coalesce(text_primary,'') || ' ' || coalesce(text_full,''))
                      @@ plainto_tsquery('german', %s)
                AND embedding IS NOT NULL
            )
            SELECT c.category_name, c.text_primary,
                   round((1 - (e.embedding <=> %s::vector))::numeric * 100, 1) as similarity_pct
            FROM candidates c
            JOIN esoteric_item e ON e.id = c.id
        """
        params = [query, emb]

        if category:
            sql = sql.replace("AND embedding IS NOT NULL", "AND embedding IS NOT NULL AND category_name ILIKE %s")
            params.insert(1, f"%{category}%")

        sql += " ORDER BY e.embedding <=> %s::vector LIMIT %s"
        params.extend([emb, limit])

        cur.execute(sql, params)
        results = cur.fetchall()
    conn.close()

    click.echo(f"\n{'Kategorie':<35} {'Similarity':>10}  Text")
    click.echo("-" * 100)
    for cat, text, sim in results:
        click.echo(f"{cat:<35} {sim:>8}%  {(text or '')[:60]}")


@cli.command()
def stats():
    """Zeigt DB-Statistiken."""
    conn = psycopg.connect(TARGET_DB)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM v_overview")
        click.echo("\n=== Uebersicht ===")
        for tbl, rows in cur.fetchall():
            click.echo(f"  {tbl:<25} {rows:>10,}")

        cur.execute("SELECT * FROM v_quality_distribution")
        click.echo("\n=== Qualitaetsverteilung ===")
        for band, items, pct in cur.fetchall():
            bar = "#" * int(pct / 2)
            click.echo(f"  {band:<25} {items:>8,} ({pct}%) {bar}")

    conn.close()


if __name__ == "__main__":
    cli()
