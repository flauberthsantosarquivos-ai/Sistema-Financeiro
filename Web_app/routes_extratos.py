from __future__ import annotations

import re
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
from core.financeiro.dashboard_base import ler_base_lancamentos, para_float
from core.financeiro.lancamentos_google import salvar_lancamentos_em_lote_google
from core.financeiro.leitor_extrato import (
    carregar_previa_extrato,
    processar_extrato,
    salvar_previa_extrato,
)
from core.financeiro.regras_classificacao import aplicar_regras_cliente_no_resultado


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

        config = obter_configuracao_sistema()
        link_planilha = config.get("planilha_google", "")

        if link_planilha:
            resultado = aplicar_regras_cliente_no_resultado(
                resultado=resultado,
                link_planilha=link_planilha,
            )

        temp_id = salvar_previa_extrato(resultado)

        qtd_regras = resultado.get("qtd_regras_cliente", 0)

        mensagem = f"Extrato lido com sucesso. {len(resultado['movimentacoes'])} movimentações identificadas."

        if qtd_regras:
            mensagem += f" {qtd_regras} regra(s) de classificação do cliente foram carregadas."

        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="previa",
                mensagem=mensagem,
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

        chaves_existentes = obter_chaves_lancamentos_existentes()

        lancamentos = []
        duplicados_ignorados = 0
        saldos_ignorados = 0

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

            data = str(mov.get("data", "")).strip()
            descricao = str(mov.get("descricao", "")).strip()
            origem = "IMPORTACAO_EXTRATO"

            if deve_ignorar_por_descricao(descricao):
                saldos_ignorados += 1
                continue

            if valor_abs <= 0:
                continue

            chave_nova = montar_chave_lancamento(
                data=data,
                descricao=descricao,
                valor=valor_abs,
            )

            if chave_nova in chaves_existentes:
                duplicados_ignorados += 1
                continue

            lancamento = {
                "data": data,
                "mes": inferir_mes(data),
                "ano": inferir_ano(data, config.get("ano_base", "")),
                "tipo": tipo,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "descricao": descricao,
                "valor_previsto": "",
                "valor_realizado": f"{valor_abs:.2f}".replace(".", ","),
                "situacao": situacao,
                "forma_pagamento": forma_pagamento,
                "conta": conta,
                "observacao": mov.get("observacao", ""),
                "origem": origem,
            }

            lancamentos.append(lancamento)
            chaves_existentes.add(chave_nova)

        if not lancamentos and (duplicados_ignorados > 0 or saldos_ignorados > 0):
            mensagem = "Nenhum lançamento novo foi importado."

            if duplicados_ignorados > 0:
                mensagem += f" {duplicados_ignorados} lançamento(s) duplicado(s) foram ignorado(s)."

            if saldos_ignorados > 0:
                mensagem += f" {saldos_ignorados} lançamento(s) de saldo foram ignorado(s)."

            return templates.TemplateResponse(
                request=request,
                name="extratos.html",
                context=montar_contexto_extratos(
                    request=request,
                    etapa="upload",
                    mensagem=mensagem,
                ),
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

        mensagem = (
            f"{len(lancamentos)} lançamento(s) importado(s) com sucesso para a BASE_LANCAMENTOS."
        )

        if duplicados_ignorados > 0:
            mensagem += f" {duplicados_ignorados} duplicado(s) foram ignorado(s)."

        if saldos_ignorados > 0:
            mensagem += f" {saldos_ignorados} lançamento(s) de saldo foram ignorado(s)."

        mensagem += f" Planilha: {url}"

        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                mensagem=mensagem,
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


def obter_chaves_lancamentos_existentes() -> set[str]:
    chaves = set()

    try:
        registros = ler_base_lancamentos()
    except Exception:
        return chaves

    for item in registros:
        data = str(item.get("DATA", "")).strip()
        descricao = str(item.get("DESCRICAO", "")).strip()

        valor_realizado = abs(para_float(item.get("VALOR_REALIZADO")))
        valor_previsto = abs(para_float(item.get("VALOR_PREVISTO")))

        valor = valor_realizado if valor_realizado > 0 else valor_previsto

        if not data or not descricao or valor <= 0:
            continue

        if deve_ignorar_por_descricao(descricao):
            continue

        chave = montar_chave_lancamento(
            data=data,
            descricao=descricao,
            valor=valor,
        )

        chaves.add(chave)

    return chaves


def montar_chave_lancamento(
    data: str,
    descricao: str,
    valor: float,
) -> str:
    data_norm = normalizar_data_para_chave(data)
    descricao_norm = normalizar_para_chave(descricao)

    valor_centavos = int(round(abs(float(valor or 0)) * 100))

    return f"{data_norm}|{descricao_norm}|{valor_centavos}"


def normalizar_data_para_chave(data: str) -> str:
    texto = str(data or "").strip()

    match_br = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", texto)
    if match_br:
        dia = match_br.group(1).zfill(2)
        mes = match_br.group(2).zfill(2)
        ano = match_br.group(3)

        if len(ano) == 2:
            ano = "20" + ano

        return f"{ano}-{mes}-{dia}"

    match_iso = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})", texto)
    if match_iso:
        ano = match_iso.group(1)
        mes = match_iso.group(2).zfill(2)
        dia = match_iso.group(3).zfill(2)

        return f"{ano}-{mes}-{dia}"

    return normalizar_para_chave(texto)


def normalizar_para_chave(valor: str) -> str:
    texto = str(valor or "").strip().upper()

    substituicoes = {
        "Á": "A",
        "À": "A",
        "Â": "A",
        "Ã": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for origem, destino in substituicoes.items():
        texto = texto.replace(origem, destino)

    texto = re.sub(r"\s+", " ", texto)
    texto = texto.strip()

    return texto


def deve_ignorar_por_descricao(descricao: str) -> bool:
    texto = normalizar_para_chave(descricao)
    texto_sem_espacos = re.sub(r"\s+", "", texto)

    termos = [
        "SALDO",
        "SALDOANTERIOR",
        "SALDOATUAL",
        "SALDODODIA",
        "SALDODISPONIVEL",
        "SALDOBLOQUEADO",
        "SALDOFINAL",
        "SALDOINICIAL",
    ]

    return any(termo in texto_sem_espacos for termo in termos)


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

    match_br = re.match(r"^\d{1,2}[/-](\d{1,2})[/-]\d{2,4}", texto)
    if match_br:
        mes = match_br.group(1).zfill(2)
        return mapa.get(mes, "")

    match_iso = re.match(r"^\d{4}[/-](\d{1,2})[/-]\d{1,2}", texto)
    if match_iso:
        mes = match_iso.group(1).zfill(2)
        return mapa.get(mes, "")

    return ""


def inferir_ano(data_texto: str, ano_padrao: str | int) -> str:
    texto = str(data_texto or "").strip()

    match_br = re.match(r"^\d{1,2}[/-]\d{1,2}[/-](\d{2,4})", texto)
    if match_br:
        ano = match_br.group(1)
        if len(ano) == 2:
            return "20" + ano
        return ano

    match_iso = re.match(r"^(\d{4})[/-]\d{1,2}[/-]\d{1,2}", texto)
    if match_iso:
        return match_iso.group(1)

    return str(ano_padrao or "")