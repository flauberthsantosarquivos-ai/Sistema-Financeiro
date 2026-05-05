from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import processar_dashboard_base


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


def mes_atual_sigla() -> str:
    hoje = date.today()

    return {
        1: "JAN",
        2: "FEV",
        3: "MAR",
        4: "ABR",
        5: "MAI",
        6: "JUN",
        7: "JUL",
        8: "AGO",
        9: "SET",
        10: "OUT",
        11: "NOV",
        12: "DEZ",
    }.get(hoje.month, "MAI")


def montar_filtros_padrao():
    config = obter_configuracao_sistema()

    return {
        "periodo_tipo": "mes_unico",
        "mes_unico": mes_atual_sigla(),
        "mes_inicio": "JAN",
        "mes_fim": "DEZ",
        "ano": str(config.get("ano_base", date.today().year)),
    }


def renderizar_dashboard(
    request: Request,
    resultado=None,
    erro=None,
    filtros=None,
):
    if filtros is None:
        filtros = montar_filtros_padrao()

    return templates.TemplateResponse(
        request=request,
        name="financeiro.html",
        context={
            "resultado": resultado,
            "erro": erro,
            "meses_opcoes": MESES_OPCOES,
            "filtros": filtros,
        },
    )


@router.get("/financeiro", response_class=HTMLResponse)
async def financeiro_get(request: Request):
    filtros = montar_filtros_padrao()

    try:
        resultado = processar_dashboard_base(
            periodo_tipo=filtros["periodo_tipo"],
            mes_unico=filtros["mes_unico"],
            mes_inicio=filtros["mes_inicio"],
            mes_fim=filtros["mes_fim"],
            ano=filtros["ano"],
        )

        return renderizar_dashboard(
            request=request,
            resultado=resultado,
            erro=None,
            filtros=filtros,
        )

    except Exception as e:
        return renderizar_dashboard(
            request=request,
            resultado=None,
            erro=f"Erro ao carregar dashboard: {e}",
            filtros=filtros,
        )


@router.post("/financeiro", response_class=HTMLResponse)
async def financeiro_post(
    request: Request,
    periodo_tipo: str = Form("mes_unico"),
    mes_unico: str = Form("MAI"),
    mes_inicio: str = Form("JAN"),
    mes_fim: str = Form("DEZ"),
    ano: str = Form("2026"),
):
    filtros = {
        "periodo_tipo": periodo_tipo,
        "mes_unico": mes_unico,
        "mes_inicio": mes_inicio,
        "mes_fim": mes_fim,
        "ano": ano,
    }

    try:
        resultado = processar_dashboard_base(
            periodo_tipo=periodo_tipo,
            mes_unico=mes_unico,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            ano=ano,
        )

        return renderizar_dashboard(
            request=request,
            resultado=resultado,
            erro=None,
            filtros=filtros,
        )

    except Exception as e:
        return renderizar_dashboard(
            request=request,
            resultado=None,
            erro=f"Erro ao carregar dashboard: {e}",
            filtros=filtros,
        )