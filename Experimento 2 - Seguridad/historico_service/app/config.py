import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://travelhub:travelhub@db:5432/travelhub")
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # TTL for session blacklist (in seconds)
    SESSION_BLACKLIST_TTL = int(os.getenv("SESSION_BLACKLIST_TTL", "3600"))
