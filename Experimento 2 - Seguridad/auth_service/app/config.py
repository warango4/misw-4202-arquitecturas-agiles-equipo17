import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "TravelhHub-Experimento-key")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://travelhub:travelhub@db:5432/travelhub")