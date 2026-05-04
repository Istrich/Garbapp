"""Aggregate v1 routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, analyze, location

api_router = APIRouter()
api_router.include_router(location.router)
api_router.include_router(analyze.router)
api_router.include_router(admin.router)
