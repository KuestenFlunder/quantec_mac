"""Pydantic schemas for the Morphic Field API."""

from pydantic import BaseModel, Field


class ThemeInfo(BaseModel):
    id: int
    name: str
    description: str | None = None
    sort_order: int | None = None


class CategoryInfo(BaseModel):
    id: int
    name: str
    theme_id: int | None = None
    theme_name: str | None = None
    parent_id: int | None = None
    depth: int | None = None
    item_count: int | None = None
    description: str | None = None


class EsotericItemInfo(BaseModel):
    id: int
    category_id: int
    category_name: str
    text_primary: str | None = None
    text_secondary: str | None = None
    quality_score: float | None = None
    similarity: float | None = None


class CategoryNeighbor(BaseModel):
    neighbor_id: int
    neighbor_name: str
    relation_type: str | None = None
    strength: float | None = None
    keyword_count: int | None = None
    shared_keywords: list[str] | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(50, ge=1, le=500)
    category: str | None = Field(None, description="Filter by category name (partial match)")
    theme: str | None = Field(None, description="Filter by theme name (partial match)")


class CategoryTreeNode(BaseModel):
    id: int
    name: str
    theme: str | None = None
    parent_name: str | None = None
    depth: int | None = None
    item_count: int | None = None
    children: list["CategoryTreeNode"] = []
