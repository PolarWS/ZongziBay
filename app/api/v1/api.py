from fastapi import APIRouter
from app.api.v1 import users, health, tmdb, magnet, piratebay, tasks, notifications, system

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(tmdb.router, prefix="/tmdb", tags=["TMDB"])
api_router.include_router(magnet.router, prefix="/magnet", tags=["Magnet"])
api_router.include_router(piratebay.router, prefix="/piratebay", tags=["PirateBay"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
