from collections.abc import Generator

from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings

engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()

# Separate metadata for querying existing tables (used by morphic API)
existing_metadata = MetaData()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reflect_existing_tables() -> None:
    """Reflect existing esoteric tables into both metadata objects.

    - Base.metadata: needed so ForeignKey('esoteric_item.id') resolves during create_all
    - existing_metadata: used by the morphic API for dynamic queries
    """
    existing_table_names = ["esoteric_item", "category", "theme", "category_relation", "item_relation"]

    # Reflect into Base.metadata so FK references resolve
    for table_name in existing_table_names:
        if table_name not in Base.metadata.tables:
            Table(table_name, Base.metadata, autoload_with=engine)

    # Also reflect into the separate metadata for morphic API queries
    existing_metadata.reflect(
        bind=engine,
        only=existing_table_names,
    )
