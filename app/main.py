from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES FIRST
# ============================================================

load_dotenv()


# ============================================================
# IMPORTS
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.wsgi import (
    WSGIMiddleware,
)

from app.api.v1.router import (
    api_router,
)

from app.core.config import (
    settings,
)

from legacy.whatsapp_payment_app import (
    app as legacy_app,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)


# ============================================================
# CORS
#
# Frontend:
#   Local:
#       http://localhost:3000
#       http://127.0.0.1:3000
#
#   Production:
#       https://biriyani-frontend-ten.vercel.app
#
# Authentication uses JWT Bearer tokens.
# We are NOT using auth cookies.
# ============================================================

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.1.4:3000",
    "https://biriyani-frontend-ten.vercel.app",
]


app.add_middleware(
    CORSMiddleware,

    allow_origins=allowed_origins,

    allow_credentials=False,

    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],

    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
    ],
)


# ============================================================
# FASTAPI V1 ROUTES
#
# Examples:
#
# /api/v1/auth/login
# /api/v1/auth/me
#
# /api/v1/dashboard/summary
#
# /api/v1/orders
# /api/v1/menu
# /api/v1/users
# /api/v1/settings
# ============================================================

app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "ok",
        "service": settings.app_name,
        "docs": "/docs",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": settings.app_name,
    }


# ============================================================
# PROJECT B WHATSAPP + RAZORPAY
#
# DO NOT CHANGE THEIR IMPLEMENTATION HERE.
#
# The Flask application inside:
#
# legacy/whatsapp_payment_app.py
#
# continues to provide:
#
# GET  /webhook
# POST /webhook
# POST /razorpay-webhook
#
# It also keeps:
#
# process_message()
# show_menu()
# send_button_message()
# send_reply()
# Razorpay payment-link creation
# Razorpay payment-success handling
# ============================================================

app.mount(
    "/",
    WSGIMiddleware(
        legacy_app
    ),
)