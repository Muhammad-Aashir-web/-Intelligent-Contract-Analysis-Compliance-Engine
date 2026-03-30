from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App Settings
    APP_NAME: str = "Intelligent Contract Analysis & Compliance Engine"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database Settings
    DATABASE_URL: str = "postgresql+psycopg2://contractuser:contractpassword@localhost:5433/contracts"
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI/LLM API Keys
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    COHERE_API_KEY: str = ""

    # Vector Database Settings
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-west1-gcp"
    PINECONE_INDEX_NAME: str = "contract-clauses"
    WEAVIATE_URL: str = ""
    WEAVIATE_API_KEY: str = ""

    # Storage Settings
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "contract-uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # Fine-tuning Settings
    WANDB_API_KEY: str = ""
    HF_TOKEN: str = ""


settings = Settings()
