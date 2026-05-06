from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.orcamento_google import (
    excluir_orcamento,
    filtrar_orcamento,
    ler_orcamento_mensal,
    montar_resumo_orcamento,
    salvar_orcamento,
)


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


MESES_OPCOES = [
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


def montar_url_retorno(mensagem: str | None = None, erro: str | None = None) -> str:
    if mensagem:
        return f"/financeiro/orcamento?mensagem={quote(mensagem)}"

    if erro:
        return f"/financeiro/orcamento?erro={quote(erro)}"

    return "/financeiro/orcamento"


@router.get("/financeiro/orcamento", response_class=HTMLResponse)
async def orcamento_get(
    request: Request,
    ano: str | None = Query(None),
    mes: str = Query(""),
    tipo: str = Query(""),
    categoria: str = Query(""),
    mensagem: str | None = Query(None),
    erro: str | None = Query(None),
):
    ano_final = ano or str(date.today().year)

    filtros = {
        "ano": ano_final,
        "mes": mes,
        "tipo": tipo,
        "categoria": categoria,
    }

    try:
        registros = ler_orcamento_mensal()

        registros_filtrados = filtrar_orcamento(
            registros=registros,
            ano=ano_final,
            mes=mes,
            tipo=tipo,
            categoria=categoria,
        )

        resumo = montar_resumo_orcamento(registros_filtrados)

        categorias_existentes = sorted(
            {
                str(item.get("CATEGORIA", "")).strip()
                for item in registros
                if str(item.get("CATEGORIA", "")).strip()
            }
        )

        return templates.TemplateResponse(
            request=request,
            name="orcamento.html",
            context={
                "erro": erro,
                "mensagem": mensagem,
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "registros": registros_filtrados,
                "resumo": resumo,
                "categorias_existentes": categorias_existentes,
                "total_registros": len(registros_filtrados),
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="orcamento.html",
            context={
                "erro": f"Erro ao carregar orçamento mensal: {e}",
                "mensagem": None,
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "registros": [],
                "resumo": montar_resumo_orcamento([]),
                "categorias_existentes": [],
                "total_registros": 0,
            },
        )


@router.post("/financeiro/orcamento/salvar")
async def orcamento_salvar_post(
    ano: str = Form(""),
    mes: str = Form(""),
    tipo: str = Form(""),
    categoria: str = Form(""),
    subcategoria: str = Form(""),
    valor_previsto: str = Form(""),
    observacao: str = Form(""),
    orcamento_id: str = Form(""),
):
    try:
        salvar_orcamento(
            ano=ano,
            mes=mes,
            tipo=tipo,
            categoria=categoria,
            subcategoria=subcategoria,
            valor_previsto=valor_previsto,
            observacao=observacao,
            orcamento_id=orcamento_id or None,
        )

        return RedirectResponse(
            url=montar_url_retorno("Orçamento salvo com sucesso."),
            status_code=303,
        )

    except Exception as e:
        return RedirectResponse(
            url=montar_url_retorno(erro=f"Erro ao salvar orçamento: {e}"),
            status_code=303,
        )


@router.post("/financeiro/orcamento/excluir/{orcamento_id}")
async def orcamento_excluir_post(
    orcamento_id: str,
):
    try:
        excluir_orcamento(orcamento_id)

        return RedirectResponse(
            url=montar_url_retorno("Item de orçamento excluído com sucesso."),
            status_code=303,
        )

    except Exception as e:
        return RedirectResponse(
            url=montar_url_retorno(erro=f"Erro ao excluir orçamento: {e}"),
            status_code=303,
        )