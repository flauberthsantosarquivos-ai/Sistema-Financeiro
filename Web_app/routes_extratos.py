from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Request, UploadFile
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
from core.financeiro.lancamentos_google import salvar_lancamentos_em_lote_google
from core.financeiro.leitor_extrato import (
    carregar_previa_extrato,
    processar_extrato,
    salvar_previa_extrato,
)


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")

PASTA_UPLOAD_EXTRATOS = Path("uploads/extratos")
PASTA_UPLOAD_EXTRATOS.mkdir(parents=True, exist_ok=True)


@router.get("/financeiro/extratos", response_class=HTMLResponse)
async def extratos_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="extratos.html",
        context=montar_contexto_extratos(
            request=request,
            etapa="upload",
        ),
    )


@router.post("/financeiro/extratos/previsualizar", response_class=HTMLResponse)
async def extratos_previsualizar(
    request: Request,
    arquivo: UploadFile = File(...),
):
    nome = arquivo.filename or ""

    if not nome.lower().endswith((".csv", ".xlsx", ".xls")):
        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                erro="Formato ainda não suportado. Envie CSV, XLS ou XLSX.",
            ),
        )

    try:
        caminho_arquivo = PASTA_UPLOAD_EXTRATOS / f"{uuid4().hex}_{nome}"

        with caminho_arquivo.open("wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)

        resultado = processar_extrato(caminho_arquivo)
        temp_id = salvar_previa_extrato(resultado)

        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="previa",
                mensagem=f"Extrato lido com sucesso. {len(resultado['movimentacoes'])} movimentações identificadas.",
                temp_id=temp_id,
                resultado=resultado,
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                erro=f"Erro ao ler extrato: {e}",
            ),
        )


@router.post("/financeiro/extratos/importar", response_class=HTMLResponse)
async def extratos_importar(request: Request):
    form = await request.form()

    temp_id = str(form.get("temp_id", "")).strip()

    try:
        previa = carregar_previa_extrato(temp_id)
        movimentacoes = previa.get("movimentacoes", [])

        config = obter_configuracao_sistema()
        link_planilha = config.get("planilha_google", "")

        if not link_planilha:
            raise ValueError("Nenhuma planilha vinculada foi encontrada nas configurações.")

        lancamentos = []

        for mov in movimentacoes:
            indice = str(mov.get("indice"))

            importar = form.get(f"importar_{indice}")

            if importar != "SIM":
                continue

            valor = float(mov.get("valor", 0))
            valor_abs = abs(valor)

            tipo = str(form.get(f"tipo_{indice}", mov.get("tipo", ""))).strip()
            categoria = str(form.get(f"categoria_{indice}", mov.get("categoria", ""))).strip()
            subcategoria = str(form.get(f"subcategoria_{indice}", mov.get("subcategoria", ""))).strip()
            situacao = str(form.get(f"situacao_{indice}", mov.get("situacao", ""))).strip()
            forma_pagamento = str(form.get(f"forma_pagamento_{indice}", mov.get("forma_pagamento", ""))).strip()
            conta = str(form.get(f"conta_{indice}", mov.get("conta", ""))).strip()

            lancamentos.append(
                {
                    "data": mov.get("data", ""),
                    "mes": inferir_mes(mov.get("data", "")),
                    "ano": inferir_ano(mov.get("data", ""), config.get("ano_base", "")),
                    "tipo": tipo,
                    "categoria": categoria,
                    "subcategoria": subcategoria,
                    "descricao": mov.get("descricao", ""),
                    "valor_previsto": "",
                    "valor_realizado": f"{valor_abs:.2f}".replace(".", ","),
                    "situacao": situacao,
                    "forma_pagamento": forma_pagamento,
                    "conta": conta,
                    "observacao": mov.get("observacao", ""),
                    "origem": "IMPORTACAO_EXTRATO",
                }
            )

        if not lancamentos:
            return templates.TemplateResponse(
                request=request,
                name="extratos.html",
                context=montar_contexto_extratos(
                    request=request,
                    etapa="previa",
                    erro="Nenhuma movimentação foi selecionada para importação.",
                    temp_id=temp_id,
                    resultado=previa,
                ),
            )

        url = salvar_lancamentos_em_lote_google(
            link_planilha=link_planilha,
            lancamentos=lancamentos,
        )

        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                mensagem=f"{len(lancamentos)} lançamentos importados com sucesso para a BASE_LANCAMENTOS. Planilha: {url}",
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                erro=f"Erro ao importar extrato: {e}",
            ),
        )


def montar_contexto_extratos(
    request: Request,
    etapa: str,
    mensagem: str | None = None,
    erro: str | None = None,
    temp_id: str | None = None,
    resultado: dict | None = None,
):
    return {
        "request": request,
        "etapa": etapa,
        "mensagem": mensagem,
        "erro": erro,
        "temp_id": temp_id,
        "resultado": resultado,
        "meses": MESES,
        "situacoes": SITUACOES,
        "formas_pagamento": FORMAS_PAGAMENTO,
        "contas": CONTAS,
        "categorias_receita": CATEGORIAS_RECEITA,
        "categorias_despesa": CATEGORIAS_DESPESA,
    }


def inferir_mes(data_texto: str) -> str:
    texto = str(data_texto or "").strip()

    mapa = {
        "01": "JAN",
        "02": "FEV",
        "03": "MAR",
        "04": "ABR",
        "05": "MAI",
        "06": "JUN",
        "07": "JUL",
        "08": "AGO",
        "09": "SET",
        "10": "OUT",
        "11": "NOV",
        "12": "DEZ",
    }

    # formatos comuns: dd/mm/aaaa, aaaa-mm-dd, dd-mm-aaaa
    match_br = re_match(r"^\d{1,2}[/-](\d{1,2})[/-]\d{2,4}", texto)
    if match_br:
        mes = match_br.group(1).zfill(2)
        return mapa.get(mes, "")

    match_iso = re_match(r"^\d{4}[/-](\d{1,2})[/-]\d{1,2}", texto)
    if match_iso:
        mes = match_iso.group(1).zfill(2)
        return mapa.get(mes, "")

    return ""


def inferir_ano(data_texto: str, ano_padrao: str | int) -> str:
    texto = str(data_texto or "").strip()

    match_br = re_match(r"^\d{1,2}[/-]\d{1,2}[/-](\d{2,4})", texto)
    if match_br:
        ano = match_br.group(1)
        if len(ano) == 2:
            return "20" + ano
        return ano

    match_iso = re_match(r"^(\d{4})[/-]\d{1,2}[/-]\d{1,2}", texto)
    if match_iso:
        return match_iso.group(1)

    return str(ano_padrao or "")


def re_match(padrao: str, texto: str):
    import re

    return re.match(padrao, texto)