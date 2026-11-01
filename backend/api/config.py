"""
api/config.py
--------------
Centralized configuration using Pydantic Settings.

All runtime configuration comes from environment variables (via .env file).
No magic numbers scattered in code — all from this module.

Usage:
    from api.config import settings
    
    db_path = settings.DB_PATH
    threshold = settings.HIGH_PRIORITY_THRESHOLD
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _PYDANTIC_SETTINGS_AVAILABLE = True
except ImportError:
    _PYDANTIC_SETTINGS_AVAILABLE = False

import os


if _PYDANTIC_SETTINGS_AVAILABLE:
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=str(Path(__file__).parent.parent / ".env"),
            env_file_encoding="utf-8",
            extra="ignore",
        )
        
        # LLM
        LLM_PROVIDER: str = "gemini"
        LLM_API_KEY: str = ""
        LLM_MODEL_NAME: str = "gemini-2.5-flash"
        LLM_BASE_URL: str = ""
        LLM_FALLBACK_MODEL: str = ""
        LLM_GROQ_API_KEY: str = ""
        LLM_GROQ_MODEL: str = "llama-3.3-70b-versatile"
        LLM_DATA_MODE: str = "anonymized"  # synthetic | anonymized | blocked
        
        # Authentication (legacy API keys)
        API_KEY_PHARMACIST: str = ""
        API_KEY_READONLY: str = ""

        # JWT (B-103)
        JWT_SECRET_KEY: str = "CHANGE_ME_in_production_min_32chars!!"
        JWT_REFRESH_SECRET_KEY: str = "CHANGE_ME_refresh_in_production!!"
        JWT_ACCESS_EXPIRE_MINUTES: int = 15
        JWT_REFRESH_EXPIRE_DAYS: int = 7

        # Service API keys (Langflow, MCP)
        SERVICE_API_KEY_LANGFLOW: str = ""
        SERVICE_API_KEY_MCP: str = ""

        # Server
        FASTAPI_HOST: str = "0.0.0.0"
        FASTAPI_PORT: int = 8000

        # Database (B-101)
        DB_PATH: str = "data/priomed.db"
        DATABASE_URL: str = "sqlite:///data/priomed.db"
        
        # ML Model
        MODEL_PATH: str = "models/"
        
        # Priority thresholds
        HIGH_PRIORITY_THRESHOLD: float = 0.7
        MEDIUM_PRIORITY_THRESHOLD: float = 0.4

    settings = Settings()

else:
    # Fallback: simple object reading from os.environ
    class _SimpleSettings:
        @property
        def LLM_PROVIDER(self): return os.getenv("LLM_PROVIDER", "gemini")
        @property
        def LLM_API_KEY(self): return os.getenv("LLM_API_KEY", "")
        @property
        def LLM_MODEL_NAME(self): return os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash")
        @property
        def LLM_BASE_URL(self): return os.getenv("LLM_BASE_URL", "")
        @property
        def LLM_FALLBACK_MODEL(self): return os.getenv("LLM_FALLBACK_MODEL", "")
        @property
        def LLM_GROQ_API_KEY(self): return os.getenv("LLM_GROQ_API_KEY", "")
        @property
        def LLM_GROQ_MODEL(self): return os.getenv("LLM_GROQ_MODEL", "llama-3.3-70b-versatile")
        @property
        def LLM_DATA_MODE(self): return os.getenv("LLM_DATA_MODE", "anonymized")
        @property
        def API_KEY_PHARMACIST(self): return os.getenv("API_KEY_PHARMACIST", "")
        @property
        def API_KEY_READONLY(self): return os.getenv("API_KEY_READONLY", "")
        @property
        def FASTAPI_HOST(self): return os.getenv("FASTAPI_HOST", "0.0.0.0")
        @property
        def FASTAPI_PORT(self): return int(os.getenv("FASTAPI_PORT", "8000"))
        @property
        def DB_PATH(self): return os.getenv("DB_PATH", "data/priomed.db")
        @property
        def MODEL_PATH(self): return os.getenv("MODEL_PATH", "models/")
        @property
        def HIGH_PRIORITY_THRESHOLD(self): return float(os.getenv("HIGH_PRIORITY_THRESHOLD", "0.7"))
        @property
        def MEDIUM_PRIORITY_THRESHOLD(self): return float(os.getenv("MEDIUM_PRIORITY_THRESHOLD", "0.4"))

    settings = _SimpleSettings()
