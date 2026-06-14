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
from mobile_api.responses import resposta_sucesso

router = APIRouter(
    prefix="/api/mobile",
    tags=["Mobile"],
)


@router.get("/status")
def status_mobile():
    return resposta_sucesso(
        dados={
            "status": "online",
            "modulo": "mobile",
        },
        mensagem="API mobile do Sistema Financeiro funcionando",
    )


@router.get("/dashboard")
def dashboard_mobile():
    dados = obter_dashboard_mobile()
    return resposta_sucesso(
        dados=dados,
        mensagem="Dashboard mobile carregado com sucesso",
    )


@router.get("/lancamentos")
def lancamentos_mobile():
    dados = listar_lancamentos_mobile()
    return resposta_sucesso(
        dados=dados,
        mensagem="Lançamentos carregados com sucesso",
    )


@router.post("/lancamentos")
def criar_lancamento(dados: dict):
    resultado = criar_lancamento_mobile(dados)
    return resposta_sucesso(
        dados=resultado,
        mensagem="Lançamento criado com sucesso",
    )


@router.get("/pagamentos")
def pagamentos_mobile():
    dados = listar_pagamentos_mobile()
    return resposta_sucesso(
        dados=dados,
        mensagem="Pagamentos carregados com sucesso",
    )


@router.patch("/pagamentos/{pagamento_id}/pagar")
def marcar_pagamento_pago(pagamento_id: int):
    resultado = marcar_pagamento_como_pago_mobile(pagamento_id)
    return resposta_sucesso(
        dados=resultado,
        mensagem="Pagamento marcado como pago com sucesso",
    )


@router.get("/orcamento")
def orcamento_mobile():
    dados = obter_orcamento_mobile()
    return resposta_sucesso(
        dados=dados,
        mensagem="Orçamento carregado com sucesso",
    )


@router.get("/patrimonio")
def patrimonio_mobile():
    dados = obter_patrimonio_mobile()
    return resposta_sucesso(
        dados=dados,
        mensagem="Patrimônio carregado com sucesso",
    )


@router.get("/metas")
def metas_mobile():
    dados = listar_metas_mobile()
    return resposta_sucesso(
        dados=dados,
        mensagem="Metas carregadas com sucesso",
    )