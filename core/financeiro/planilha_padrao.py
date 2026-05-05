from __future__ import annotations

from pathlib import Path

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from core.financeiro.categorias import (
    CATEGORIAS_DESPESA,
    CATEGORIAS_RECEITA,
    CONTAS,
    FORMAS_PAGAMENTO,
    ORCAMENTO_PADRAO,
    SITUACOES,
)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH = Path("token_financeiro_sheets.json")


def autenticar_sheets() -> gspread.Client:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "credentials.json não encontrado na raiz do SISTEMA FINANCEIRO."
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


def formatar_cabecalho(planilha, aba, total_colunas: int):
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": aba.id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": total_colunas,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {
                            "red": 0.06,
                            "green": 0.18,
                            "blue": 0.35,
                        },
                        "horizontalAlignment": "CENTER",
                        "textFormat": {
                            "foregroundColor": {
                                "red": 1,
                                "green": 1,
                                "blue": 1,
                            },
                            "bold": True,
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": aba.id,
                    "gridProperties": {
                        "frozenRowCount": 1,
                    },
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": aba.id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": total_colunas,
                }
            }
        },
    ]

    planilha.batch_update({"requests": requests})


def criar_aba(planilha, nome: str, linhas: int = 1000, colunas: int = 20):
    try:
        aba = planilha.worksheet(nome)
        aba.clear()
        return aba
    except gspread.WorksheetNotFound:
        return planilha.add_worksheet(title=nome, rows=linhas, cols=colunas)


def montar_linhas_categorias() -> list[list[str]]:
    linhas = [["TIPO", "CATEGORIA", "SUBCATEGORIA", "ATIVO"]]

    for categoria, subcategorias in CATEGORIAS_RECEITA.items():
        for subcategoria in subcategorias:
            linhas.append(["RECEITA", categoria, subcategoria, "SIM"])

    for categoria, subcategorias in CATEGORIAS_DESPESA.items():
        for subcategoria in subcategorias:
            linhas.append(["DESPESA", categoria, subcategoria, "SIM"])

    return linhas


def montar_linhas_contas() -> list[list[str]]:
    linhas = [["CONTA", "TIPO", "BANCO", "ATIVO", "OBSERVACAO"]]

    for conta in CONTAS:
        tipo = "CONTA/CARTEIRA"

        if "HIPERCARD" in conta:
            tipo = "CARTÃO"
        elif conta in {"COFRE", "EM MÃOS"}:
            tipo = "DINHEIRO"
        elif "ALIMENTAÇÃO" in conta:
            tipo = "CONTA RESERVA"
        elif "PRINCIPAL" in conta:
            tipo = "CONTA PRINCIPAL"

        linhas.append([conta, tipo, "", "SIM", ""])

    return linhas


def montar_linhas_orcamento_padrao() -> list[list[str]]:
    linhas = [
        [
            "ATIVO",
            "TIPO",
            "CATEGORIA",
            "SUBCATEGORIA",
            "DESCRICAO",
            "VALOR_PADRAO",
            "SITUACAO_PADRAO",
            "FORMA_PAGAMENTO",
            "CONTA",
            "DIA_BASE",
            "ORIGEM",
            "OBSERVACAO",
        ]
    ]

    for item in ORCAMENTO_PADRAO:
        linhas.append(
            [
                "SIM",
                item.get("tipo", ""),
                item.get("categoria", ""),
                item.get("subcategoria", ""),
                item.get("descricao", ""),
                item.get("valor_padrao", ""),
                item.get("situacao", ""),
                item.get("forma_pagamento", ""),
                item.get("conta", ""),
                str(item.get("dia_base", "")),
                "ORCAMENTO_PADRAO",
                item.get("observacao", ""),
            ]
        )

    return linhas


def criar_planilha_padrao_financeira(
    nome_cliente: str,
    ano_base: int,
    receita_padrao: str,
    conta_principal: str,
    conta_alimentacao: str,
    meta_reserva: str,
) -> dict:
    cliente = autenticar_sheets()

    nome_planilha = f"SISTEMA FINANCEIRO - {nome_cliente} - {ano_base}"
    planilha = cliente.create(nome_planilha)

    # Se existir aba padrão vazia, remove depois que criar as abas oficiais.
    abas_iniciais = planilha.worksheets()

    aba_config = criar_aba(planilha, "CONFIGURACOES", linhas=100, colunas=5)
    aba_categorias = criar_aba(planilha, "CATEGORIAS", linhas=500, colunas=10)
    aba_contas = criar_aba(planilha, "CONTAS", linhas=200, colunas=10)
    aba_orcamento = criar_aba(planilha, "ORCAMENTO_PADRAO", linhas=500, colunas=20)
    aba_base = criar_aba(planilha, "BASE_LANCAMENTOS", linhas=2000, colunas=20)
    aba_resumo = criar_aba(planilha, "RESUMO_MENSAL", linhas=200, colunas=20)
    aba_dash = criar_aba(planilha, "DASHBOARD_PLANILHA", linhas=200, colunas=20)

    # Remove a Sheet1 padrão, se ainda existir e não for uma das oficiais.
    for aba in abas_iniciais:
        if aba.title not in {
            "CONFIGURACOES",
            "CATEGORIAS",
            "CONTAS",
            "ORCAMENTO_PADRAO",
            "BASE_LANCAMENTOS",
            "RESUMO_MENSAL",
            "DASHBOARD_PLANILHA",
        }:
            try:
                planilha.del_worksheet(aba)
            except Exception:
                pass

    aba_config.update(
        "A1:B7",
        [
            ["PARAMETRO", "VALOR"],
            ["NOME_CLIENTE", nome_cliente],
            ["ANO_BASE", str(ano_base)],
            ["RECEITA_PADRAO", receita_padrao],
            ["CONTA_PRINCIPAL", conta_principal],
            ["CONTA_ALIMENTACAO", conta_alimentacao],
            ["META_RESERVA_PERCENTUAL", meta_reserva],
        ],
    )

    linhas_categorias = montar_linhas_categorias()
    aba_categorias.update(
        f"A1:D{len(linhas_categorias)}",
        linhas_categorias,
    )

    linhas_contas = montar_linhas_contas()
    aba_contas.update(
        f"A1:E{len(linhas_contas)}",
        linhas_contas,
    )

    linhas_orcamento = montar_linhas_orcamento_padrao()
    aba_orcamento.update(
        f"A1:L{len(linhas_orcamento)}",
        linhas_orcamento,
    )

    cabecalhos_base = [
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
    aba_base.update("A1:P1", [cabecalhos_base])

    cabecalhos_resumo = [
        "MES",
        "ANO",
        "RECEITA_PREVISTA",
        "RECEITA_REALIZADA",
        "DESPESA_PREVISTA",
        "DESPESA_REALIZADA",
        "RESERVADO_ALIMENTACAO",
        "SALDO_PREVISTO",
        "SALDO_REALIZADO",
        "META_RESERVA",
        "DIAGNOSTICO",
    ]
    aba_resumo.update("A1:K1", [cabecalhos_resumo])

    aba_dash.update(
        "A1:B6",
        [
            ["DASHBOARD_PLANILHA", "Uso opcional"],
            ["Observação", "O dashboard principal será exibido no sistema web."],
            ["Fonte oficial", "BASE_LANCAMENTOS"],
            ["Orçamento padrão", "ORCAMENTO_PADRAO"],
            ["Resumo", "RESUMO_MENSAL"],
            ["Status", "Criado automaticamente pelo sistema."],
        ],
    )

    formatar_cabecalho(planilha, aba_config, 2)
    formatar_cabecalho(planilha, aba_categorias, 4)
    formatar_cabecalho(planilha, aba_contas, 5)
    formatar_cabecalho(planilha, aba_orcamento, 12)
    formatar_cabecalho(planilha, aba_base, 16)
    formatar_cabecalho(planilha, aba_resumo, 11)
    formatar_cabecalho(planilha, aba_dash, 2)

    return {
        "nome": nome_planilha,
        "url": planilha.url,
        "id": planilha.id,
    }