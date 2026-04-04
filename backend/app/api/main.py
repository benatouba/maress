from fastapi import APIRouter

from app.api.routes import gis, items, login, private, regions, study_sites, tags, users, utils
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(tags.router)
api_router.include_router(study_sites.router)
api_router.include_router(regions.router)
api_router.include_router(gis.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
