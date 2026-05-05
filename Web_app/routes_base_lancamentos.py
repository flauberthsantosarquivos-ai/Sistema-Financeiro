from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import (
    filtrar_por_periodo,
    formatar_moeda,
    ler_base_lancamentos,
    para_float,
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


def preparar_linhas(registros: list[dict]) -> list[dict]:
    linhas = []

    for item in registros:
        valor_previsto = abs(para_float(item.get("VALOR_PREVISTO")))
        valor_realizado = abs(para_float(item.get("VALOR_REALIZADO")))

        linhas.append(
            {
                "id": item.get("ID", ""),
                "data": item.get("DATA", ""),
                "mes": item.get("MES", ""),
                "ano": item.get("ANO", ""),
                "tipo": item.get("TIPO", ""),
                "categoria": item.get("CATEGORIA", ""),
                "subcategoria": item.get("SUBCATEGORIA", ""),
                "descricao": item.get("DESCRICAO", ""),
                "valor_previsto": valor_previsto,
                "valor_realizado": valor_realizado,
                "valor_previsto_fmt": formatar_moeda(valor_previsto),
                "valor_realizado_fmt": formatar_moeda(valor_realizado),
                "situacao": item.get("SITUACAO", ""),
                "forma_pagamento": item.get("FORMA_PAGAMENTO", ""),
                "conta": item.get("CONTA", ""),
                "origem": item.get("ORIGEM", ""),
                "observacao": item.get("OBSERVACAO", ""),
                "criado_em": item.get("CRIADO_EM", ""),
            }
        )

    return linhas


@router.get("/financeiro/base-lancamentos", response_class=HTMLResponse)
async def base_lancamentos_get(
    request: Request,
    periodo_tipo: str = Query("todos"),
    mes_unico: str = Query("MAI"),
    mes_inicio: str = Query("JAN"),
    mes_fim: str = Query("DEZ"),
    ano: str | None = Query(None),
):
    config = obter_configuracao_sistema()
    ano_final = ano or str(config.get("ano_base", date.today().year))

    filtros = {
        "periodo_tipo": periodo_tipo,
        "mes_unico": mes_unico,
        "mes_inicio": mes_inicio,
        "mes_fim": mes_fim,
        "ano": ano_final,
    }

    try:
        registros = ler_base_lancamentos()

        registros_filtrados = filtrar_por_periodo(
            registros=registros,
            periodo_tipo=periodo_tipo,
            mes_unico=mes_unico,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            ano=ano_final,
        )

        linhas = preparar_linhas(registros_filtrados)

        total_previsto = sum(item["valor_previsto"] for item in linhas)
        total_realizado = sum(item["valor_realizado"] for item in linhas)

        return templates.TemplateResponse(
            request=request,
            name="base_lancamentos.html",
            context={
                "erro": None,
                "linhas": linhas,
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "total_registros": len(linhas),
                "total_previsto_fmt": formatar_moeda(total_previsto),
                "total_realizado_fmt": formatar_moeda(total_realizado),
                "planilha_google": config.get("planilha_google", ""),
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="base_lancamentos.html",
            context={
                "erro": f"Erro ao carregar BASE_LANCAMENTOS: {e}",
                "linhas": [],
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "total_registros": 0,
                "total_previsto_fmt": formatar_moeda(0),
                "total_realizado_fmt": formatar_moeda(0),
                "planilha_google": config.get("planilha_google", ""),
            },
        )