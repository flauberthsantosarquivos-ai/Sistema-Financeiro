from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.metas_google import (
    CATEGORIAS_METAS,
    PRIORIDADES_METAS,
    STATUS_METAS,
    excluir_meta_financeira,
    listar_metas_financeiras,
    salvar_meta_financeira,
    sugerir_metas_automaticas,
)


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


def resumo_vazio() -> dict:
    return {
        "metas": [],
        "total_metas": 0,
        "total_ativas": 0,
        "total_concluidas": 0,
        "total_atencao": 0,
        "total_alvo": 0,
        "total_alvo_fmt": "R$ 0,00",
        "total_atual": 0,
        "total_atual_fmt": "R$ 0,00",
        "total_faltante": 0,
        "total_faltante_fmt": "R$ 0,00",
        "percentual_geral": 0,
        "percentual_geral_fmt": "0,0%",
    }


def contexto_base(
    request: Request,
    mensagem: str | None = None,
    erro: str | None = None,
    diagnostico_sugestao: dict | None = None,
) -> dict:
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    resumo = resumo_vazio()

    if link_planilha:
        try:
            resumo = listar_metas_financeiras(link_planilha)
        except Exception as e:
            erro = erro or f"Não foi possível carregar as metas financeiras: {e}"
    else:
        erro = erro or (
            "Nenhuma planilha vinculada. Configure a planilha da Central Financeira "
            "antes de cadastrar metas."
        )

    return {
        "request": request,
        "mensagem": mensagem,
        "erro": erro,
        "link_planilha": link_planilha,
        "resumo": resumo,
        "metas": resumo.get("metas", []),
        "categorias": CATEGORIAS_METAS,
        "prioridades": PRIORIDADES_METAS,
        "status_opcoes": STATUS_METAS,
        "diagnostico_sugestao": diagnostico_sugestao,
    }


@router.get("/financeiro/metas", response_class=HTMLResponse)
async def metas_get(
    request: Request,
    salvo: str | None = Query(None),
    excluido: str | None = Query(None),
):
    mensagem = None

    if salvo == "1":
        mensagem = "Meta financeira salva com sucesso."

    if excluido == "1":
        mensagem = "Meta financeira excluída com sucesso."

    return templates.TemplateResponse(
        request=request,
        name="metas.html",
        context=contexto_base(
            request=request,
            mensagem=mensagem,
            diagnostico_sugestao=None,
        ),
    )


@router.post("/financeiro/metas", response_class=HTMLResponse)
async def metas_post(
    request: Request,
    nome_meta: str = Form(...),
    categoria: str = Form(...),
    valor_alvo: str = Form(...),
    valor_atual: str = Form(""),
    data_alvo: str = Form(""),
    prioridade: str = Form(...),
    status: str = Form(...),
    observacao: str = Form(""),
):
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    if not link_planilha:
        return templates.TemplateResponse(
            request=request,
            name="metas.html",
            context=contexto_base(
                request=request,
                erro=(
                    "Nenhuma planilha vinculada. Configure a planilha da Central Financeira "
                    "antes de cadastrar metas."
                ),
            ),
        )

    try:
        salvar_meta_financeira(
            link_planilha=link_planilha,
            dados={
                "nome_meta": nome_meta,
                "categoria": categoria,
                "valor_alvo": valor_alvo,
                "valor_atual": valor_atual,
                "data_alvo": data_alvo,
                "prioridade": prioridade,
                "status": status,
                "observacao": observacao,
            },
        )

        return RedirectResponse(
            url="/financeiro/metas?salvo=1",
            status_code=303,
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="metas.html",
            context=contexto_base(
                request=request,
                erro=f"Erro ao salvar meta financeira: {e}",
            ),
        )


@router.post("/financeiro/metas/sugerir", response_class=HTMLResponse)
async def metas_sugerir_post(
    request: Request,
):
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    if not link_planilha:
        return templates.TemplateResponse(
            request=request,
            name="metas.html",
            context=contexto_base(
                request=request,
                erro=(
                    "Nenhuma planilha vinculada. Configure a planilha da Central Financeira "
                    "antes de sugerir metas automaticamente."
                ),
            ),
        )

    try:
        resultado = sugerir_metas_automaticas(link_planilha=link_planilha)

        quantidade_cadastrada = int(resultado.get("quantidade_cadastrada", 0))
        quantidade_ignorada = int(resultado.get("quantidade_ignorada", 0))

        if quantidade_cadastrada > 0:
            mensagem = (
                f"{quantidade_cadastrada} meta(s) financeira(s) sugerida(s) automaticamente "
                "e cadastrada(s) com sucesso. Veja abaixo o diagnóstico dos dados usados."
            )
        elif quantidade_ignorada > 0:
            mensagem = (
                "Nenhuma nova meta automática foi cadastrada porque as metas sugeridas "
                "já existiam. Veja abaixo o diagnóstico dos dados analisados."
            )
        else:
            mensagem = (
                "Nenhuma nova meta automática foi cadastrada. "
                "Veja abaixo o diagnóstico dos dados analisados."
            )

        return templates.TemplateResponse(
            request=request,
            name="metas.html",
            context=contexto_base(
                request=request,
                mensagem=mensagem,
                diagnostico_sugestao=resultado,
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="metas.html",
            context=contexto_base(
                request=request,
                erro=f"Erro ao sugerir metas automaticamente: {e}",
                diagnostico_sugestao=None,
            ),
        )


@router.post("/financeiro/metas/excluir", response_class=HTMLResponse)
async def metas_excluir_post(
    meta_id: str = Form(...),
):
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    if not link_planilha:
        return RedirectResponse(
            url="/financeiro/metas",
            status_code=303,
        )

    try:
        excluir_meta_financeira(
            link_planilha=link_planilha,
            meta_id=meta_id,
        )

        return RedirectResponse(
            url="/financeiro/metas?excluido=1",
            status_code=303,
        )

    except Exception:
        return RedirectResponse(
            url="/financeiro/metas",
            status_code=303,
        )