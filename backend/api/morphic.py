"""Morphic Field Browser API -- semantic, fulltext, and hybrid search.

Endpoints:
  GET /morphic/themes           -- list all theme groups
  GET /morphic/categories       -- list categories (filterable)
  GET /morphic/categories/tree  -- hierarchical category tree
  GET /morphic/items/{cat_id}   -- list items in a category
  GET /morphic/search           -- unified search (semantic/fulltext/hybrid)
  GET /morphic/neighbors/{cat}  -- category neighbors via shared keywords
"""

from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Table, func, select, text
from sqlalchemy.orm import Session

from database import existing_metadata, get_db
from schemas.morphic import (
    CategoryInfo,
    CategoryNeighbor,
    CategoryTreeNode,
    EsotericItemInfo,
    ThemeInfo,
)

router = APIRouter()


class SearchType(str, Enum):
    semantic = "semantic"
    fulltext = "fulltext"
    hybrid = "hybrid"


def _get_table(name: str) -> Table:
    table = existing_metadata.tables.get(name)
    if table is None:
        raise HTTPException(status_code=500, detail=f"Table '{name}' not reflected")
    return table


# ── Themes ──────────────────────────────────────────────────────

@router.get("/themes", response_model=list[ThemeInfo])
def list_themes(db: Session = Depends(get_db)):
    theme = _get_table("theme")
    stmt = select(theme).order_by(theme.c.sort_order)
    rows = db.execute(stmt).mappings().all()
    return [ThemeInfo(**row) for row in rows]


# ── Categories ──────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryInfo])
def list_categories(
    theme_id: int | None = None,
    parent_id: int | None = None,
    db: Session = Depends(get_db),
):
    category = _get_table("category")
    theme = _get_table("theme")
    stmt = (
        select(
            category.c.id,
            category.c.name,
            category.c.theme_id,
            theme.c.name.label("theme_name"),
            category.c.parent_id,
            category.c.depth,
            category.c.item_count,
            category.c.description,
        )
        .outerjoin(theme, category.c.theme_id == theme.c.id)
        .order_by(category.c.name)
    )
    if theme_id is not None:
        stmt = stmt.where(category.c.theme_id == theme_id)
    if parent_id is not None:
        stmt = stmt.where(category.c.parent_id == parent_id)
    rows = db.execute(stmt).mappings().all()
    return [CategoryInfo(**row) for row in rows]


@router.get("/categories/tree", response_model=list[CategoryTreeNode])
def category_tree(
    theme_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Build hierarchical category tree."""
    category = _get_table("category")
    theme = _get_table("theme")
    stmt = (
        select(
            category.c.id,
            category.c.name,
            theme.c.name.label("theme"),
            category.c.parent_id,
            category.c.depth,
            category.c.item_count,
        )
        .outerjoin(theme, category.c.theme_id == theme.c.id)
        .order_by(category.c.theme_id, category.c.name)
    )
    if theme_id is not None:
        stmt = stmt.where(category.c.theme_id == theme_id)

    rows = db.execute(stmt).mappings().all()

    # Build tree structure
    nodes: dict[int, dict] = {}
    roots: list[dict] = []

    for row in rows:
        node = {
            "id": row["id"],
            "name": row["name"],
            "theme": row["theme"],
            "parent_name": None,
            "depth": row["depth"],
            "item_count": row["item_count"],
            "children": [],
        }
        nodes[row["id"]] = node

    for row in rows:
        node = nodes[row["id"]]
        parent_id = row["parent_id"]
        if parent_id and parent_id in nodes:
            node["parent_name"] = nodes[parent_id]["name"]
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots


# ── Items per Category ──────────────────────────────────────────

@router.get("/items/{category_id}", response_model=list[EsotericItemInfo])
def list_category_items(
    category_id: int,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    esoteric_item = _get_table("esoteric_item")
    category = _get_table("category")

    cat_check = db.execute(
        select(category.c.id).where(category.c.id == category_id)
    ).first()
    if not cat_check:
        raise HTTPException(status_code=404, detail="Category not found")

    stmt = (
        select(
            esoteric_item.c.id,
            esoteric_item.c.category_id,
            esoteric_item.c.category_name,
            esoteric_item.c.text_primary,
            esoteric_item.c.text_secondary,
            esoteric_item.c.quality_score,
        )
        .where(esoteric_item.c.category_id == category_id)
        .order_by(esoteric_item.c.text_primary)
        .offset(skip)
        .limit(limit)
    )
    rows = db.execute(stmt).mappings().all()
    return [EsotericItemInfo(**row) for row in rows]


# ── Category Neighbors ──────────────────────────────────────────

@router.get("/neighbors/{category_id}", response_model=list[CategoryNeighbor])
def category_neighbors(
    category_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get related categories via shared keywords (uses DB function)."""
    stmt = text("SELECT * FROM category_neighbors(:cat_id, :n)")
    rows = db.execute(stmt, {"cat_id": category_id, "n": limit}).mappings().all()
    return [CategoryNeighbor(**row) for row in rows]


# ── Unified Search ──────────────────────────────────────────────

@router.get("/search", response_model=list[EsotericItemInfo])
def search_items(
    q: str = Query(..., min_length=1, description="Search query"),
    type: SearchType = SearchType.hybrid,
    limit: int = Query(50, ge=1, le=500),
    category: str | None = Query(None, description="Category name filter"),
    theme: str | None = Query(None, description="Theme name filter"),
    db: Session = Depends(get_db),
):
    """Unified search endpoint supporting semantic, fulltext, and hybrid modes."""
    if type == SearchType.fulltext:
        return _fulltext_search(q, limit, category, db)
    elif type == SearchType.semantic:
        return _semantic_search(q, limit, category, theme, db)
    else:
        return _hybrid_search(q, limit, category, db)


def _fulltext_search(
    q: str, limit: int, category: str | None, db: Session
) -> list[EsotericItemInfo]:
    """German fulltext search using GIN index via DB function."""
    if category:
        stmt = text("""
            SELECT f.id, f.category_name, f.text_primary, f.rank AS similarity,
                   e.category_id, e.text_secondary, e.quality_score
            FROM fulltext_search(:query, :lim) f
            JOIN esoteric_item e ON e.id = f.id
            WHERE f.category_name ILIKE :cat_pattern
        """)
        rows = db.execute(stmt, {
            "query": q, "lim": limit * 3, "cat_pattern": f"%{category}%"
        }).mappings().all()
        results = list(rows)[:limit]
    else:
        stmt = text("""
            SELECT f.id, f.category_name, f.text_primary, f.rank AS similarity,
                   e.category_id, e.text_secondary, e.quality_score
            FROM fulltext_search(:query, :lim) f
            JOIN esoteric_item e ON e.id = f.id
        """)
        rows = db.execute(stmt, {"query": q, "lim": limit}).mappings().all()
        results = list(rows)

    return [EsotericItemInfo(**row) for row in results]


def _semantic_search(
    q: str, limit: int, category: str | None, theme: str | None, db: Session
) -> list[EsotericItemInfo]:
    """Semantic search using pgvector cosine similarity with real embeddings.

    Ported from quantec_vector/scripts/search.py:semantic().
    """
    from services.embedding_service import embed_query

    emb = embed_query(q)

    sql = """
        SELECT e.id, e.category_id, e.category_name, e.text_primary,
               e.text_secondary, e.quality_score,
               round((1 - (e.embedding <=> :emb::vector))::numeric * 100, 1) as similarity
        FROM esoteric_item e
        WHERE e.embedding IS NOT NULL
    """
    params: dict = {"emb": str(emb), "lim": limit}

    if category:
        sql += " AND e.category_name ILIKE :cat_pattern"
        params["cat_pattern"] = f"%{category}%"
    if theme:
        sql += """
            AND e.category_id IN (
                SELECT c.id FROM category c
                WHERE c.theme_id IN (
                    SELECT t.id FROM theme t WHERE t.name ILIKE :theme_pattern
                )
            )
        """
        params["theme_pattern"] = f"%{theme}%"

    sql += " ORDER BY e.embedding <=> :emb2::vector LIMIT :lim"
    params["emb2"] = str(emb)

    try:
        rows = db.execute(text(sql), params).mappings().all()
        return [EsotericItemInfo(**row) for row in rows]
    except Exception:
        # Fallback to fulltext if embedding service unavailable
        return _fulltext_search(q, limit, category, db)


def _hybrid_search(
    q: str, limit: int, category: str | None, db: Session
) -> list[EsotericItemInfo]:
    """Hybrid search: fulltext pre-filter + vector ranking.

    Ported from quantec_vector/scripts/search.py:hybrid().
    Uses German tsvector for candidate selection, then ranks by cosine similarity.
    """
    from services.embedding_service import embed_query

    emb = embed_query(q)

    sql = """
        WITH candidates AS (
            SELECT id, category_id, category_name, text_primary,
                   text_secondary, quality_score
            FROM esoteric_item
            WHERE to_tsvector('german', coalesce(text_primary,'') || ' ' || coalesce(text_full,''))
                  @@ plainto_tsquery('german', :query)
            AND embedding IS NOT NULL
    """
    params: dict = {"query": q, "emb": str(emb), "lim": limit}

    if category:
        sql += " AND category_name ILIKE :cat_pattern"
        params["cat_pattern"] = f"%{category}%"

    sql += """
        )
        SELECT c.id, c.category_id, c.category_name, c.text_primary,
               c.text_secondary, c.quality_score,
               round((1 - (e.embedding <=> :emb::vector))::numeric * 100, 1) as similarity
        FROM candidates c
        JOIN esoteric_item e ON e.id = c.id
        ORDER BY e.embedding <=> :emb2::vector
        LIMIT :lim
    """
    params["emb2"] = str(emb)

    try:
        rows = db.execute(text(sql), params).mappings().all()
        results = [EsotericItemInfo(**row) for row in rows]
        # If hybrid returns nothing (no fulltext matches), fall back to semantic
        if not results:
            return _semantic_search(q, limit, category, None, db)
        return results
    except Exception:
        return _fulltext_search(q, limit, category, db)
