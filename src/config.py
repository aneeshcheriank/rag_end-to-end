from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    """Application settings, driven by environment variables / `.env`.

    Field names are lowercase snake_case; pydantic-settings maps them to
    matching UPPER_CASE environment variables automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_model_path: str = "./models"

    # LLM
    llm_model: str = "deepseek-v4-flash"
    # Model used by DeepEval for metric computation (must support JSON
    # structured output). deepseek-chat handles this reliably;
    # deepseek-v4-flash does not.
    eval_model: str = "deepseek-v4-pro"
    deepseek_api_key: str = SecretStr

    # Retrieval
    top_k: int = 4

    # Infrastructure
    database_url: str = (
        "postgresql+psycopg://rag:rag@localhost:5432/rag?sslmode=disable"
    )
    redis_url: str = "redis://localhost:6379/0"

    # Auth (used in later phases)
    jwt_secret: str = SecretStr
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None


settings = Settings()
