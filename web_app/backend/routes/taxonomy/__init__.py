# pyrefly: ignore [missing-import]
from fastapi import APIRouter

from .build_taxonomy import router as build_taxonomy_router
from .get_status import router as get_status_router
from .get_taxonomy import router as get_taxonomy_router
from .download_excel import router as download_excel_router
from .preview_excel import router as preview_excel_router
from .rename_run import router as rename_run_router
from .get_runs import router as get_runs_router
from .get_analytics import router as get_analytics_router
from .download_export import router as download_export_router

router = APIRouter(tags=["Taxonomy API"])

router.include_router(build_taxonomy_router)
router.include_router(get_status_router)
router.include_router(get_taxonomy_router)
router.include_router(download_excel_router)
router.include_router(preview_excel_router)
router.include_router(rename_run_router)
router.include_router(get_runs_router)
router.include_router(get_analytics_router)
router.include_router(download_export_router)
