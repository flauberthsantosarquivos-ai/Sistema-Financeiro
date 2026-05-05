from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.categorias import (
    CATEGORIAS_DESPESA,
    CATEGORIAS_RECEITA,
    CONTAS,
    FORMAS_PAGAMENTO,
    MESES,
    SITUACOES,
)
from core.financeiro.lancamentos_google import salvar_lancamento_google


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


@router.get("/financeiro/lancamento", response_class=HTMLResponse)
async def novo_lancamento_get(request: Request):
    hoje = date.today()
    config = obter_configuracao_sistema()

    return templates.TemplateResponse(
        request=request,
        name="lancamento.html",
        context={
            "mensagem": None,
            "erro": None,
            "hoje": hoje.isoformat(),
            "ano_atual": int(config.get("ano_base", hoje.year)),
            "link_planilha": config.get("planilha_google", ""),
            "meses": MESES,
            "situacoes": SITUACOES,
            "formas_pagamento": FORMAS_PAGAMENTO,
            "contas": CONTAS,
            "categorias_receita": CATEGORIAS_RECEITA,
            "categorias_despesa": CATEGORIAS_DESPESA,
        },
    )


@router.post("/financeiro/lancamento", response_class=HTMLResponse)
async def novo_lancamento_post(
    request: Request,
    link_planilha: str = Form(...),
    data: str = Form(...),
    mes: str = Form(...),
    ano: str = Form(...),
    tipo: str = Form(...),
    categoria: str = Form(...),
    subcategoria: str = Form(...),
    descricao: str = Form(...),
    valor_previsto: str = Form(""),
    valor_realizado: str = Form(""),
    situacao: str = Form(...),
    forma_pagamento: str = Form(...),
    conta: str = Form(...),
    observacao: str = Form(""),
):
    config = obter_configuracao_sistema()
    link_planilha_final = config.get("planilha_google") or link_planilha

    try:
        dados = {
            "data": data,
            "mes": mes,
            "ano": ano,
            "tipo": tipo,
            "categoria": categoria,
            "subcategoria": subcategoria,
            "descricao": descricao,
            "valor_previsto": valor_previsto,
            "valor_realizado": valor_realizado,
            "situacao": situacao,
            "forma_pagamento": forma_pagamento,
            "conta": conta,
            "observacao": observacao,
            "origem": "MANUAL",
        }

        url = salvar_lancamento_google(
            link_planilha=link_planilha_final,
            dados=dados,
        )

        hoje = date.today()

        return templates.TemplateResponse(
            request=request,
            name="lancamento.html",
            context={
                "mensagem": f"Lançamento salvo com sucesso na planilha: {url}",
                "erro": None,
                "hoje": hoje.isoformat(),
                "ano_atual": int(config.get("ano_base", hoje.year)),
                "link_planilha": link_planilha_final,
                "meses": MESES,
                "situacoes": SITUACOES,
                "formas_pagamento": FORMAS_PAGAMENTO,
                "contas": CONTAS,
                "categorias_receita": CATEGORIAS_RECEITA,
                "categorias_despesa": CATEGORIAS_DESPESA,
            },
        )

    except Exception as e:
        hoje = date.today()

        return templates.TemplateResponse(
            request=request,
            name="lancamento.html",
            context={
                "mensagem": None,
                "erro": f"Erro ao salvar lançamento: {e}",
                "hoje": hoje.isoformat(),
                "ano_atual": int(config.get("ano_base", hoje.year)),
                "link_planilha": link_planilha_final,
                "meses": MESES,
                "situacoes": SITUACOES,
                "formas_pagamento": FORMAS_PAGAMENTO,
                "contas": CONTAS,
                "categorias_receita": CATEGORIAS_RECEITA,
                "categorias_despesa": CATEGORIAS_DESPESA,
            },
        )