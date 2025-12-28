"""
Project JobHunter V3 - Configuration Settings
Loads environment variables and defines application settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # =========================================================================
    # Application
    # =========================================================================
    APP_NAME: str = "Project JobHunter"
    APP_VERSION: str = "3.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    
    # =========================================================================
    # API
    # =========================================================================
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,chrome-extension://*"
    
    # =========================================================================
    # PostgreSQL (V3 - Long-Term Memory & World Model)
    # =========================================================================
    POSTGRES_USER: str = "jobhunter"
    POSTGRES_PASSWORD: str = "jobhunter_secret"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "jobhunter_db"
    
    @property
    def DATABASE_URL(self) -> str:
        """Async PostgreSQL connection string."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync PostgreSQL connection string (for Celery/Alembic)."""
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # =========================================================================
    # Redis (V3 - Task Queue & Short-Term Memory)
    # =========================================================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    @property
    def REDIS_URL(self) -> str:
        """Redis connection string."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
    
    @property
    def CELERY_BROKER_URL(self) -> str:
        """Celery broker URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
    
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Celery result backend URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"
    
    # =========================================================================
    # Qdrant (V3 - Vector Memory)
    # =========================================================================
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    
    @property
    def QDRANT_URL(self) -> str:
        """Qdrant REST API URL."""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
    
    # =========================================================================
    # AI/LLM Providers
    # =========================================================================
    # Groq API (Free LLM inference - Speed)
    GROQ_API_KEY: str = ""
    
    # OpenAI (For GPT-4o Vision - Quality)
    OPENAI_API_KEY: Optional[str] = None
    
    # Anthropic (Alternative reasoning)
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # Model Configuration
    LLM_MODEL_FAST: str = "llama-3.1-8b-instant"      # Fast DOM analysis
    LLM_MODEL_REASONING: str = "llama-3.3-70b-versatile"  # Complex questions
    LLM_MODEL_VISION: str = "gpt-4o"                   # Visual analysis
    
    # Legacy aliases
    @property
    def LLM_MODEL_COMPLEX(self) -> str:
        return self.LLM_MODEL_REASONING
    
    @property
    def LLM_MODEL_SIMPLE(self) -> str:
        return self.LLM_MODEL_FAST
    
    # =========================================================================
    # ChromaDB (Legacy V1 - Keep for compatibility)
    # =========================================================================
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"
    
    # =========================================================================
    # Embedding Model (free, local via HuggingFace)
    # =========================================================================
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # =========================================================================
    # Playwright (Browser Automation)
    # =========================================================================
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_SLOW_MO: int = 0  # ms delay between actions
    
    # =========================================================================
    # Rate Limiting & Cost Management
    # =========================================================================
    MAX_TOKENS_PER_USER_MONTHLY: int = 100000
    MAX_APPLICATIONS_PER_HOUR: int = 20
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
