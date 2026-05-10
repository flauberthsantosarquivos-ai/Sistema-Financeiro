from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.analise_investimentos import montar_analise_investimentos
from core.financeiro.patrimonio_google import MESES_OPCOES


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


@router.get("/financeiro/investimentos", response_class=HTMLResponse)
async def investimentos_get(
    request: Request,
    ano: str | None = Query(None),
    mes: str | None = Query(None),
):
    ano_final = str(ano or date.today().year)
    mes_final = mes or obter_mes_atual_sigla()

    try:
        analise = montar_analise_investimentos(
            ano=ano_final,
            mes=mes_final,
        )

        return templates.TemplateResponse(
            request=request,
            name="investimentos.html",
            context={
                "erro": None,
                "ano": ano_final,
                "mes": mes_final,
                "meses_opcoes": MESES_OPCOES,
                "analise": analise,
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="investimentos.html",
            context={
                "erro": f"Erro ao montar análise de investimentos: {e}",
                "ano": ano_final,
                "mes": mes_final,
                "meses_opcoes": MESES_OPCOES,
                "analise": None,
            },
        )


def obter_mes_atual_sigla() -> str:
    indice = date.today().month - 1
    return MESES_OPCOES[indice][0]