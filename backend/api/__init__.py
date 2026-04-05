from fastapi import APIRouter

from api.clients import router as clients_router
from api.morphic import router as morphic_router
from api.scan import router as scan_router
from api.send import router as send_router
from api.sheets import router as sheets_router
from api.targets import router as targets_router

api_router = APIRouter()

api_router.include_router(clients_router, prefix="/clients", tags=["Clients"])
api_router.include_router(targets_router, prefix="/targets", tags=["Targets"])
api_router.include_router(sheets_router, prefix="/sheets", tags=["Healing Sheets"])
api_router.include_router(morphic_router, prefix="/morphic", tags=["Morphic Field"])
api_router.include_router(scan_router, prefix="/scan", tags=["Scan"])
api_router.include_router(send_router, prefix="/send", tags=["Send"])
