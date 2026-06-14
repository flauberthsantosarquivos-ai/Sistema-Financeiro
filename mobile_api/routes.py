from fastapi import APIRouter

from mobile_api.dashboard_service import obter_dashboard_mobile

router = APIRouter(
    prefix="/api/mobile",
    tags=["Mobile"],
)


@router.get("/status")
def status_mobile():
    return {
        "status": "online",
        "modulo": "mobile",
        "mensagem": "API mobile do Sistema Financeiro funcionando",
    }


@router.get("/dashboard")
def dashboard_mobile():
    return obter_dashboard_mobile()