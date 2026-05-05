from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH = Path("token_financeiro_sheets.json")

NOME_ABA_BASE = "BASE_LANCAMENTOS"

CABECALHOS_BASE = [
    "ID",
    "DATA",
    "MES",
    "ANO",
    "TIPO",
    "CATEGORIA",
    "SUBCATEGORIA",
    "DESCRICAO",
    "VALOR_PREVISTO",
    "VALOR_REALIZADO",
    "SITUACAO",
    "FORMA_PAGAMENTO",
    "CONTA",
    "ORIGEM",
    "OBSERVACAO",
    "CRIADO_EM",
]


def extrair_id_planilha(link_ou_id: str) -> str:
    texto = (link_ou_id or "").strip()

    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", texto)

    if match:
        return match.group(1)

    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", texto):
        return texto

    raise ValueError("Não foi possível identificar o ID da planilha Google.")


def autenticar_sheets() -> gspread.Client:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "credentials.json não encontrado na pasta do sistema financeiro."
        )

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return gspread.authorize(creds)


def abrir_planilha(link_planilha: str):
    spreadsheet_id = extrair_id_planilha(link_planilha)
    cliente = autenticar_sheets()
    return cliente.open_by_key(spreadsheet_id)


def obter_ou_criar_base(planilha):
    try:
        aba = planilha.worksheet(NOME_ABA_BASE)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(
            title=NOME_ABA_BASE,
            rows=2000,
            cols=len(CABECALHOS_BASE),
        )
        aba.update("A1:P1", [CABECALHOS_BASE])
        return aba

    valores = aba.get_all_values()

    if not valores:
        aba.update("A1:P1", [CABECALHOS_BASE])
        return aba

    cabecalhos_atuais = [item.strip().upper() for item in valores[0]]

    if cabecalhos_atuais[: len(CABECALHOS_BASE)] != CABECALHOS_BASE:
        aba.update("A1:P1", [CABECALHOS_BASE])

    return aba


def normalizar_valor(valor: str | float | int | None) -> str:
    if valor is None:
        return ""

    texto = str(valor).strip()

    if not texto:
        return ""

    texto = texto.replace("R$", "").replace(" ", "")

    return texto


def montar_linha_lancamento(dados: dict[str, Any]) -> list[str]:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return [
        dados.get("id") or uuid4().hex,
        dados.get("data", ""),
        dados.get("mes", ""),
        dados.get("ano", ""),
        dados.get("tipo", ""),
        dados.get("categoria", ""),
        dados.get("subcategoria", ""),
        dados.get("descricao", ""),
        normalizar_valor(dados.get("valor_previsto", "")),
        normalizar_valor(dados.get("valor_realizado", "")),
        dados.get("situacao", ""),
        dados.get("forma_pagamento", ""),
        dados.get("conta", ""),
        dados.get("origem", "MANUAL"),
        dados.get("observacao", ""),
        dados.get("criado_em") or agora,
    ]


def ler_registros_base(aba) -> list[dict[str, Any]]:
    """
    Lê a BASE_LANCAMENTOS sem usar get_all_records(),
    para evitar erro quando a planilha tiver cabeçalhos duplicados
    deixados por versões anteriores.
    """
    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        return []

    registros = []

    for linha in valores[1:]:
        if not any(str(celula).strip() for celula in linha):
            continue

        linha_completa = linha + [""] * (len(CABECALHOS_BASE) - len(linha))

        registro = {
            cabecalho: linha_completa[indice]
            for indice, cabecalho in enumerate(CABECALHOS_BASE)
        }

        registros.append(registro)

    return registros


def salvar_lancamento_google(
    link_planilha: str,
    dados: dict[str, Any],
) -> str:
    planilha = abrir_planilha(link_planilha)
    aba = obter_ou_criar_base(planilha)

    linha = montar_linha_lancamento(dados)

    aba.append_row(
        linha,
        value_input_option="USER_ENTERED",
    )

    return planilha.url


def abrir_planilha_e_base(link_planilha: str):
    planilha = abrir_planilha(link_planilha)
    aba = obter_ou_criar_base(planilha)

    return planilha, aba


def existe_planejamento_do_mes(
    link_planilha: str,
    mes: str,
    ano: str,
) -> bool:
    _, aba = abrir_planilha_e_base(link_planilha)

    registros = ler_registros_base(aba)

    mes = mes.strip().upper()
    ano = str(ano).strip()

    for item in registros:
        item_mes = str(item.get("MES", "")).strip().upper()
        item_ano = str(item.get("ANO", "")).strip()
        item_origem = str(item.get("ORIGEM", "")).strip().upper()

        if item_mes == mes and item_ano == ano and item_origem == "ORCAMENTO_PADRAO":
            return True

    return False


def salvar_lancamentos_em_lote_google(
    link_planilha: str,
    lancamentos: list[dict[str, Any]],
) -> str:
    planilha = abrir_planilha(link_planilha)
    aba = obter_ou_criar_base(planilha)

    linhas = [montar_linha_lancamento(dados) for dados in lancamentos]

    if linhas:
        aba.append_rows(
            linhas,
            value_input_option="USER_ENTERED",
        )

    return planilha.url