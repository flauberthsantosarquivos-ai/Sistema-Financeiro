from fastapi import APIRouter, Query

from mobile_api.alimentacao_service import obter_alimentacao_mobile
from mobile_api.dashboard_service import obter_dashboard_mobile
from mobile_api.lancamentos_service import criar_lancamento_mobile, listar_lancamentos_mobile
from mobile_api.metas_service import listar_metas_mobile
from mobile_api.orcamento_service import obter_orcamento_mobile
from mobile_api.pagamentos_service import listar_pagamentos_mobile, marcar_pagamento_como_pago_mobile
from mobile_api.painel_gerencial_service import obter_painel_gerencial_mobile
from mobile_api.patrimonio_service import obter_patrimonio_mobile
from mobile_api.responses import resposta_sucesso

router = APIRouter(prefix="/api/mobile", tags=["Mobile"])


@router.get("/status")
def status_mobile():
    return resposta_sucesso(
        dados={"status": "online", "modulo": "mobile", "versao": "fase-mobile-1.7"},
        mensagem="API mobile do Sistema Financeiro funcionando",
    )


@router.get("/dashboard")
def dashboard_mobile(ano: int | None = Query(None), mes: int | None = Query(None, ge=1, le=12)):
    return resposta_sucesso(dados=obter_dashboard_mobile(ano=ano, mes=mes), mensagem="Dashboard mobile carregado com sucesso")


@router.get("/painel-gerencial")
def painel_gerencial_mobile(ano: int | None = Query(None), mes: int | None = Query(None, ge=1, le=12)):
    return resposta_sucesso(dados=obter_painel_gerencial_mobile(ano=ano, mes=mes), mensagem="Painel gerencial mobile carregado com sucesso")


@router.get("/alimentacao")
def alimentacao_mobile(ano: int | None = Query(None, description="Ano de referência"), mes: int | None = Query(None, ge=1, le=12, description="Mês de referência")):
    return resposta_sucesso(dados=obter_alimentacao_mobile(ano=ano, mes=mes), mensagem="Alimentação mobile carregada com sucesso")


@router.get("/lancamentos")
def lancamentos_mobile(ano: int | None = Query(None), mes: int | None = Query(None, ge=1, le=12)):
    return resposta_sucesso(dados=listar_lancamentos_mobile(ano=ano, mes=mes), mensagem="Lançamentos carregados com sucesso")


@router.post("/lancamentos")
def criar_lancamento(dados: dict):
    return resposta_sucesso(dados=criar_lancamento_mobile(dados), mensagem="Lançamento criado com sucesso")


@router.get("/pagamentos")
def pagamentos_mobile(ano: int | None = Query(None), mes: int | None = Query(None, ge=1, le=12)):
    return resposta_sucesso(dados=listar_pagamentos_mobile(ano=ano, mes=mes), mensagem="Pagamentos carregados com sucesso")


@router.patch("/pagamentos/{pagamento_id}/pagar")
def marcar_pagamento_pago(pagamento_id: int):
    return resposta_sucesso(dados=marcar_pagamento_como_pago_mobile(pagamento_id), mensagem="Pagamento marcado como pago com sucesso")


@router.get("/orcamento")
def orcamento_mobile(ano: int | None = Query(None), mes: int | None = Query(None, ge=1, le=12)):
    return resposta_sucesso(dados=obter_orcamento_mobile(ano=ano, mes=mes), mensagem="Orçamento carregado com sucesso")


@router.get("/patrimonio")
def patrimonio_mobile(ano: int | None = Query(None), mes: int | None = Query(None, ge=1, le=12)):
    return resposta_sucesso(dados=obter_patrimonio_mobile(ano=ano, mes=mes), mensagem="Patrimônio carregado com sucesso")


@router.get("/metas")
def metas_mobile(ano: int | None = Query(None), mes: int | None = Query(None, ge=1, le=12)):
    return resposta_sucesso(dados=listar_metas_mobile(ano=ano, mes=mes), mensagem="Metas carregadas com sucesso")
