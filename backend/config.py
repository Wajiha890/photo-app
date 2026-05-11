import os


class Config:
    db_url = os.environ.get("DATABASE_URL", "sqlite:///media.db")
    # SQLAlchemy requires postgresql:// (not legacy postgres://)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "pixshare-secret-key-change-in-prod")
    JWT_EXPIRY_HOURS = 24

    # Comma-separated origins, or "*" for all (dev only). Example: https://app.azurestaticapps.net
    CORS_ORIGINS_RAW = os.environ.get("CORS_ORIGINS", "*")

    # Azure Blob Storage — private container + SAS URLs for media uploads
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

    # Azure PostgreSQL requires TLS; auto-enable for Azure hostnames unless URL already sets sslmode.
    _engine_options = {}
    if db_url.startswith("postgresql") and "sslmode=" not in db_url.lower():
        sslmode = os.environ.get("POSTGRES_SSLMODE", "").strip().lower()
        if not sslmode and "database.azure.com" in db_url.lower():
            sslmode = "require"
        if sslmode and sslmode not in ("disable", "false", "0"):
            _engine_options["connect_args"] = {"sslmode": sslmode}
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options