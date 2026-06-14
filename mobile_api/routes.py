from fastapi import APIRouter

from mobile_api.dashboard_service import obter_dashboard_mobile
from mobile_api.lancamentos_service import (
    criar_lancamento_mobile,
    listar_lancamentos_mobile,
)
from mobile_api.metas_service import listar_metas_mobile
from mobile_api.orcamento_service import obter_orcamento_mobile
from mobile_api.pagamentos_service import (
    listar_pagamentos_mobile,
    marcar_pagamento_como_pago_mobile,
)
from mobile_api.patrimonio_service import obter_patrimonio_mobile

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


@router.get("/lancamentos")
def lancamentos_mobile():
    return listar_lancamentos_mobile()


@router.post("/lancamentos")
def criar_lancamento(dados: dict):
    return criar_lancamento_mobile(dados)


@router.get("/pagamentos")
def pagamentos_mobile():
    return listar_pagamentos_mobile()


@router.patch("/pagamentos/{pagamento_id}/pagar")
def marcar_pagamento_pago(pagamento_id: int):
    return marcar_pagamento_como_pago_mobile(pagamento_id)


@router.get("/orcamento")
def orcamento_mobile():
    return obter_orcamento_mobile()


@router.get("/patrimonio")
def patrimonio_mobile():
    return obter_patrimonio_mobile()


@router.get("/metas")
def metas_mobile():
    return listar_metas_mobile()