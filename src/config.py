import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct")
    DM_PASSWORD: str = os.getenv("DM_PASSWORD", "changeme")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-secret-key")
    DB_PATH: str = os.getenv("DB_PATH", "data/campaigns.db")
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "data/chroma_db")


settings = Settings()
