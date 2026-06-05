from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.patrimonio_google import (
    ATIVOS_PATRIMONIO,
    MESES_OPCOES,
    copiar_patrimonio_mes,
    dados_formulario_padrao,
    montar_itens_formulario_padrao,
    montar_resumo_patrimonio,
    salvar_patrimonio_mensal,
)


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


@router.get("/financeiro/patrimonio", response_class=HTMLResponse)
async def patrimonio_get(
    request: Request,
    ano: str | None = Query(None),
    mes: str | None = Query(None),
    modo: str | None = Query(None),
    salvo: str | None = Query(None),
    erro: str | None = Query(None),
    ano_resumo: str | None = Query(None),
    mes_resumo: str | None = Query(None),
):
    config = obter_configuracao_sistema()

    ano_atual = str(date.today().year)
    mes_atual = obter_mes_atual_sigla()

    ano_base = str(config.get("ano_base") or ano_atual)

    ano_resumo_final = str(ano_resumo or ano or ano_base)
    mes_resumo_final = mes_resumo or mes or mes_atual

    ano_final = str(ano or ano_resumo_final or ano_base)
    mes_final = mes or mes_resumo_final or mes_atual

    modo_final = str(modo or "consultar").strip().lower()

    resumo = montar_resumo_patrimonio(
        ano=ano_resumo_final,
        ano_resumo=ano_resumo_final,
        mes_resumo=mes_resumo_final,
    )

    if modo_final == "editar":
        dados_formulario = dados_formulario_padrao(
            ano=ano_final,
            mes=mes_final,
        )
        formulario_aberto = True
    else:
        dados_formulario = {
            "ANO": ano_final,
            "MES": mes_final,
            "DATA_INICIO": "",
            "DATA_FIM": "",
            "OBSERVACAO": "",
            "ITENS": montar_itens_formulario_padrao(),
        }
        formulario_aberto = False
        modo_final = "consultar"

    return templates.TemplateResponse(
        request=request,
        name="patrimonio.html",
        context={
            "erro": erro,
            "salvo": salvo,
            "config": config,
            "ano": ano_final,
            "mes": mes_final,
            "modo": modo_final,
            "formulario_aberto": formulario_aberto,
            "ano_resumo": ano_resumo_final,
            "mes_resumo": mes_resumo_final,
            "meses_opcoes": MESES_OPCOES,
            "ativos_patrimonio": ATIVOS_PATRIMONIO,
            "dados_formulario": dados_formulario,
            "resumo": resumo,
            "planilha_google": config.get("planilha_google", ""),
        },
    )


@router.post("/financeiro/patrimonio/copiar")
async def patrimonio_copiar(
    ano_origem: str = Form(...),
    mes_origem: str = Form(...),
    ano_destino: str = Form(...),
    mes_destino: str = Form(...),
):
    try:
        resultado = copiar_patrimonio_mes(
            ano_origem=ano_origem,
            mes_origem=mes_origem,
            ano_destino=ano_destino,
            mes_destino=mes_destino,
        )

        return RedirectResponse(
            url=(
                f"/financeiro/patrimonio?"
                f"ano={resultado['ano']}&"
                f"mes={resultado['mes']}&"
                f"ano_resumo={resultado['ano']}&"
                f"mes_resumo={resultado['mes']}&"
                f"modo=editar&"
                f"salvo=copiado"
            ),
            status_code=303,
        )

    except Exception as e:
        return RedirectResponse(
            url=(
                f"/financeiro/patrimonio?"
                f"ano_resumo={ano_destino}&"
                f"mes_resumo={mes_destino}&"
                f"erro=Erro ao copiar patrimônio: {e}"
            ),
            status_code=303,
        )


@router.post("/financeiro/patrimonio/salvar")
async def patrimonio_salvar(
    request: Request,
    ano: str = Form(...),
    mes: str = Form(...),
    data_inicio: str = Form(""),
    data_fim: str = Form(""),
    observacao: str = Form(""),
):
    form = await request.form()

    dados = {
        "ANO": ano,
        "MES": mes,
        "DATA_INICIO": data_inicio,
        "DATA_FIM": data_fim,
        "OBSERVACAO": observacao,
        "ITENS": [],
    }

    ativos = form.getlist("ativo[]")
    subdivisoes = form.getlist("subdivisao[]")
    valores_inicio = form.getlist("valor_inicio[]")
    valores_fim = form.getlist("valor_fim[]")
    observacoes_item = form.getlist("observacao_item[]")

    maior_tamanho = max(
        len(ativos),
        len(subdivisoes),
        len(valores_inicio),
        len(valores_fim),
        len(observacoes_item),
        0,
    )

    for indice in range(maior_tamanho):
        ativo = ativos[indice] if indice < len(ativos) else ""
        subdivisao = subdivisoes[indice] if indice < len(subdivisoes) else ""
        valor_inicio = valores_inicio[indice] if indice < len(valores_inicio) else ""
        valor_fim = valores_fim[indice] if indice < len(valores_fim) else ""
        observacao_item = (
            observacoes_item[indice] if indice < len(observacoes_item) else ""
        )

        if not str(ativo or "").strip():
            continue

        dados["ITENS"].append(
            {
                "ATIVO": ativo,
                "SUBDIVISAO": subdivisao,
                "VALOR_INICIO": valor_inicio,
                "VALOR_FIM": valor_fim,
                "OBSERVACAO": observacao_item,
            }
        )

    try:
        resultado = salvar_patrimonio_mensal(dados)

        return RedirectResponse(
            url=(
                f"/financeiro/patrimonio?"
                f"ano_resumo={resultado['ano']}&"
                f"mes_resumo={resultado['mes']}&"
                f"salvo={resultado['acao']}"
            ),
            status_code=303,
        )

    except Exception as e:
        config = obter_configuracao_sistema()

        ano_final = str(ano or config.get("ano_base") or date.today().year)
        mes_final = mes or obter_mes_atual_sigla()

        resumo = montar_resumo_patrimonio(
            ano=ano_final,
            ano_resumo=ano_final,
            mes_resumo=mes_final,
        )

        dados_formulario = {
            "ANO": ano,
            "MES": mes,
            "DATA_INICIO": data_inicio,
            "DATA_FIM": data_fim,
            "OBSERVACAO": observacao,
            "ITENS": dados["ITENS"],
        }

        return templates.TemplateResponse(
            request=request,
            name="patrimonio.html",
            context={
                "erro": f"Erro ao salvar patrimônio financeiro: {e}",
                "salvo": None,
                "config": config,
                "ano": ano_final,
                "mes": mes_final,
                "modo": "editar",
                "formulario_aberto": True,
                "ano_resumo": ano_final,
                "mes_resumo": mes_final,
                "meses_opcoes": MESES_OPCOES,
                "ativos_patrimonio": ATIVOS_PATRIMONIO,
                "dados_formulario": dados_formulario,
                "resumo": resumo,
                "planilha_google": config.get("planilha_google", ""),
            },
        )


def obter_mes_atual_sigla() -> str:
    indice = date.today().month - 1
    return MESES_OPCOES[indice][0]