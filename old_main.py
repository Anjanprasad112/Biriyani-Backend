from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES FIRST
# ============================================================

load_dotenv()


# ============================================================
# IMPORTS
# ============================================================

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

from app.api.v1.router import api_router

from legacy.whatsapp_payment_app import (
    app as legacy_app,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

fastapi_app = FastAPI(
    title="Watave's Biryani API",
    version="1.0.0",
    description=(
        "Watave's Biryani order management API"
    ),
)


# ============================================================
# FASTAPI V1 ROUTES
#
# /api/v1/auth
# /api/v1/dashboard
# /api/v1/orders
# /api/v1/menu
# /api/v1/settings
# /api/v1/users
# ============================================================

fastapi_app.include_router(
    api_router,
    prefix="/api/v1",
)


# ============================================================
# ROOT
# ============================================================

@fastapi_app.get("/")
def root():

    return {
        "status": "ok",
        "service": "Watave's Biryani API",
        "docs": "/docs",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@fastapi_app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "Watave's Biryani API",
    }


# ============================================================
# LEGACY WHATSAPP + RAZORPAY
#
# WhatsApp / Razorpay functionality remains inside:
#
# legacy/whatsapp_payment_app.py
#
# Routes:
#
# GET  /webhook
# POST /webhook
# POST /razorpay-webhook
#
# We are NOT changing their logic here.
# ============================================================

fastapi_app.mount(
    "/",
    WSGIMiddleware(
        legacy_app
    ),
)


# ============================================================
# GLOBAL CORS WRAPPER
#
# IMPORTANT:
#
# This wraps the ENTIRE application.
#
# Local development:
#   http://localhost:3000
#   http://127.0.0.1:3000
#
# Production frontend will also work.
#
# Authentication uses JWT Bearer tokens, NOT cookies,
# therefore credentials are disabled.
# ============================================================

app = CORSMiddleware(
    app=fastapi_app,

    allow_origins=[
        "*",
    ],

    allow_credentials=False,

    allow_methods=[
        "*",
    ],

    allow_headers=[
        "*",
    ],

    allow_private_network=True,
)