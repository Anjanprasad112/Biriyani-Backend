import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# LOAD .ENV
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=False,
)


# ============================================================
# SETTINGS
# ============================================================

class Settings:

    # --------------------------------------------------------
    # APPLICATION
    # --------------------------------------------------------

    app_name: str = os.getenv(
        "APP_NAME",
        "Watave's Biryani API",
    )

    app_environment: str = os.getenv(
        "APP_ENVIRONMENT",
        "development",
    )

    api_v1_prefix: str = os.getenv(
        "API_V1_PREFIX",
        "/api/v1",
    )

    app_timezone: str = os.getenv(
        "APP_TIMEZONE",
        "Asia/Kolkata",
    )

    default_shop_id: int = int(
        os.getenv(
            "DEFAULT_SHOP_ID",
            "1",
        )
    )


    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    database_url: str | None = os.getenv(
        "DATABASE_URL"
    )


    # --------------------------------------------------------
    # JWT
    # --------------------------------------------------------

    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY",
        "change-this-before-production",
    )

    jwt_algorithm: str = os.getenv(
        "JWT_ALGORITHM",
        "HS256",
    )

    access_token_expire_minutes: int = int(
        os.getenv(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "720",
        )
    )


    # --------------------------------------------------------
    # WHATSAPP
    # --------------------------------------------------------

    access_token: str | None = os.getenv(
        "ACCESS_TOKEN"
    )

    phone_number_id: str | None = os.getenv(
        "PHONE_NUMBER_ID"
    )

    verify_token: str | None = os.getenv(
        "VERIFY_TOKEN"
    )

    whatsapp_graph_api_version: str = os.getenv(
        "WHATSAPP_GRAPH_API_VERSION",
        "v20.0",
    )


    # --------------------------------------------------------
    # RAZORPAY
    # --------------------------------------------------------

    razorpay_key_id: str | None = os.getenv(
        "RAZORPAY_KEY_ID"
    )

    razorpay_key_secret: str | None = os.getenv(
        "RAZORPAY_KEY_SECRET"
    )

    razorpay_webhook_secret: str | None = os.getenv(
        "RAZORPAY_WEBHOOK_SECRET"
    )


    # --------------------------------------------------------
    # FRONTEND / CORS
    # --------------------------------------------------------

    frontend_origins: str = os.getenv(
        "FRONTEND_ORIGINS",
        (
            "http://localhost:5173,"
            "http://127.0.0.1:5173,"
            "http://localhost:3000,"
            "http://127.0.0.1:3000"
        ),
    )


    @property
    def cors_origins(
        self,
    ) -> list[str]:

        return [
            origin.strip()
            for origin
            in self.frontend_origins.split(",")
            if origin.strip()
        ]


# ============================================================
# SETTINGS INSTANCE
# ============================================================

settings = Settings()


# ============================================================
# REQUIRED CONFIG VALIDATION
# ============================================================

if not settings.database_url:

    raise RuntimeError(
        "DATABASE_URL is missing from .env"
    )