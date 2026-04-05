from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "QUANTEC PRO Mac"
    app_version: str = "1.0.0"
    debug: bool = True

    db_host: str = "localhost"
    db_port: int = 5434
    db_name: str = "quantec_vector"
    db_user: str = "quantec"
    db_password: str = "quantec_vec_2026"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]
    api_prefix: str = "/api"
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000


settings = Settings()
