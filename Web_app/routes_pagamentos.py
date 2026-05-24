"""
Rotas do Módulo de Pagamentos

Arquivo sugerido:
Web_app/routes_pagamentos.py

Integração no app.py:
from Web_app.routes_pagamentos import router as pagamentos_router
app.include_router(pagamentos_router)
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.pagamentos_google import (
    MESES_ORDEM,
    STATUS_PAGAMENTO,
    conciliar_pagamentos_com_lancamentos,
    excluir_pagamento,
    listar_pagamentos,
    montar_resumo_pagamentos,
    obter_opcoes_categorias,
    salvar_pagamento,
)


router = APIRouter(prefix="/financeiro", tags=["Financeiro - Pagamentos"])
templates = Jinja2Templates(directory="Web_app/templates")


def redirect_pagamentos(params: Optional[str] = None):
    url = "/financeiro/pagamentos"
    if params:
        url += f"?{params}"
    return RedirectResponse(url=url, status_code=303)


def filtros_padrao(
    ano: Optional[int] = None,
    mes: Optional[str] = None,
    status: Optional[str] = None,
    tipo: Optional[str] = None,
    categoria: Optional[str] = None,
):
    hoje = date.today()

    return {
        "ano": str(ano or hoje.year),
        "mes": (mes or MESES_ORDEM[hoje.month - 1]).upper(),
        "status": (status or "").upper(),
        "tipo": (tipo or "").upper(),
        "categoria": (categoria or "").upper(),
    }


@router.get("/pagamentos")
async def tela_pagamentos(
    request: Request,
    ano: Optional[int] = Query(None),
    mes: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    categoria: Optional[str] = Query(None),
    mensagem: Optional[str] = Query(None),
    erro: Optional[str] = Query(None),
):
    filtros = filtros_padrao(ano=ano, mes=mes, status=status, tipo=tipo, categoria=categoria)

    try:
        pagamentos = listar_pagamentos(filtros)
        resumo = montar_resumo_pagamentos(pagamentos)
        categorias = obter_opcoes_categorias()
    except Exception as exc:
        pagamentos = []
        resumo = montar_resumo_pagamentos([])
        categorias = {}
        erro = erro or f"Erro ao carregar pagamentos: {exc}"

    tipos_opcoes = ["", "DESPESA", "RECEITA", "INVESTIMENTO", "TRANSFERÊNCIA"]
    meses_opcoes = [
        ("JAN", "Janeiro"),
        ("FEV", "Fevereiro"),
        ("MAR", "Março"),
        ("ABR", "Abril"),
        ("MAI", "Maio"),
        ("JUN", "Junho"),
        ("JUL", "Julho"),
        ("AGO", "Agosto"),
        ("SET", "Setembro"),
        ("OUT", "Outubro"),
        ("NOV", "Novembro"),
        ("DEZ", "Dezembro"),
    ]

    return templates.TemplateResponse(
        request=request,
        name="pagamentos.html",
        context={
            "request": request,
            "filtros": filtros,
            "pagamentos": pagamentos,
            "resumo": resumo,
            "categorias": categorias,
            "status_opcoes": [""] + STATUS_PAGAMENTO,
            "tipos_opcoes": tipos_opcoes,
            "meses_opcoes": meses_opcoes,
            "mensagem": mensagem,
            "erro": erro,
        },
    )


@router.post("/pagamentos/salvar")
async def salvar_pagamento_rota(
    pagamento_id: str = Form(""),
    ano: str = Form(...),
    mes: str = Form(...),
    descricao: str = Form(...),
    tipo: str = Form(...),
    categoria: str = Form(...),
    subcategoria: str = Form(""),
    valor_previsto: str = Form(...),
    valor_pago: str = Form("0"),
    data_vencimento: str = Form(...),
    data_pagamento: str = Form(""),
    status: str = Form("PENDENTE"),
    recorrente: str = Form("NÃO"),
    conta_pagamento: str = Form(""),
    observacao: str = Form(""),
):
    try:
        salvar_pagamento(
            {
                "id": pagamento_id,
                "ano": ano,
                "mes": mes,
                "descricao": descricao,
                "tipo": tipo,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "valor_previsto": valor_previsto,
                "valor_pago": valor_pago,
                "data_vencimento": data_vencimento,
                "data_pagamento": data_pagamento,
                "status": status,
                "recorrente": recorrente,
                "conta_pagamento": conta_pagamento,
                "observacao": observacao,
            }
        )
        return redirect_pagamentos(
            f"ano={ano}&mes={mes}&modo=cadastrar&mensagem=Pagamento salvo com sucesso"
        )
    except Exception as exc:
        return redirect_pagamentos(
            f"ano={ano}&mes={mes}&modo=cadastrar&erro={str(exc)}"
        )


@router.post("/pagamentos/{pagamento_id}/pagar")
async def marcar_pago_rota(pagamento_id: str):
    from core.financeiro.pagamentos_google import atualizar_status_pagamento

    try:
        atualizar_status_pagamento(pagamento_id, "PAGO")
        return redirect_pagamentos("mensagem=Pagamento marcado como pago e identificado como encontrado")
    except Exception as exc:
        return redirect_pagamentos(f"erro={str(exc)}")


@router.post("/pagamentos/{pagamento_id}/cancelar")
async def cancelar_pagamento_rota(pagamento_id: str):
    from core.financeiro.pagamentos_google import atualizar_status_pagamento

    try:
        atualizar_status_pagamento(pagamento_id, "CANCELADO")
        return redirect_pagamentos("mensagem=Pagamento cancelado")
    except Exception as exc:
        return redirect_pagamentos(f"erro={str(exc)}")


@router.post("/pagamentos/{pagamento_id}/excluir")
async def excluir_pagamento_rota(pagamento_id: str):
    try:
        excluir_pagamento(pagamento_id)
        return redirect_pagamentos("mensagem=Pagamento excluído")
    except Exception as exc:
        return redirect_pagamentos(f"erro={str(exc)}")


@router.post("/pagamentos/conciliar")
async def conciliar_pagamentos_rota(
    ano: str = Form(""),
    mes: str = Form(""),
    status: str = Form(""),
    tipo: str = Form(""),
    categoria: str = Form(""),
):
    try:
        resultado = conciliar_pagamentos_com_lancamentos(
            {
                "ano": ano,
                "mes": mes,
                "status": status,
                "tipo": tipo,
                "categoria": categoria,
            },
            aplicar_alteracoes=True,
        )
        mensagem = resultado.get("mensagem", "Conferência concluída.")
        return redirect_pagamentos(f"ano={ano}&mes={mes}&mensagem={mensagem}")
    except Exception as exc:
        return redirect_pagamentos(f"ano={ano}&mes={mes}&modo=cadastrar&erro={str(exc)}")