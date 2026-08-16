from fastapi import (
    APIRouter,
)

from app.api.v1.endpoints import (
    auth,
    dashboard,
    menu,
    orders,
    settings,
    users,
)


api_router = APIRouter()


api_router.include_router(
    auth.router
)

api_router.include_router(
    dashboard.router
)

api_router.include_router(
    orders.router
)

api_router.include_router(
    menu.router
)

api_router.include_router(
    settings.router
)

api_router.include_router(
    users.router
)