import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    database_url: str = os.getenv("DATABASE_URL", "")
    group_id: int = int(os.getenv("GROUP_ID", "0") or "0")
    owner_id: int = int(os.getenv("OWNER_ID", "5264127517"))
    spontaneous_probability: float = float(os.getenv("SPONTANEOUS_PROBABILITY", "0.10"))
    global_cooldown_seconds: int = int(os.getenv("GLOBAL_COOLDOWN_SECONDS", "35"))
    user_cooldown_seconds: int = int(os.getenv("USER_COOLDOWN_SECONDS", "180"))
    max_replies_per_hour: int = int(os.getenv("MAX_REPLIES_PER_HOUR", "18"))

settings = Settings()
