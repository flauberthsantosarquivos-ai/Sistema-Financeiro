from __future__ import annotations

import re
from pathlib import Path

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


LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1J9UkEfD4B1WefHfo5eQ6jnu6wUgYWkhMXJ6UU3kSC9A/edit?gid=694834181#gid=694834181"


CABECALHOS_BASE = [
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
    "OBSERVACAO",
]


EXEMPLOS_BASE = [
    [
        "01/05/2026",
        "MAI",
        "2026",
        "RECEITA",
        "SALÁRIO",
        "TRE",
        "Salário mensal",
        "23117,07",
        "23117,07",
        "RECEBIDO",
        "CONTA",
        "BANCO DO BRASIL",
        "Exemplo de receita",
    ],
    [
        "03/05/2026",
        "MAI",
        "2026",
        "DESPESA",
        "ALIMENTAÇÃO",
        "SUPERMERCADO",
        "Compra de supermercado",
        "800,00",
        "750,00",
        "PAGO",
        "CARTÃO",
        "HIPERCARD",
        "Exemplo de despesa",
    ],
    [
        "04/05/2026",
        "MAI",
        "2026",
        "DESPESA",
        "OUTROS",
        "DIVERSOS",
        "Teste categoria outros",
        "300,00",
        "300,00",
        "PAGO",
        "PIX",
        "BANCO DO BRASIL",
        "Exemplo para testar OUTROS no dashboard",
    ],
    [
        "05/05/2026",
        "MAI",
        "2026",
        "DESPESA",
        "TRANSPORTE",
        "COMBUSTÍVEL",
        "Gasolina",
        "400,00",
        "380,00",
        "PAGO",
        "DÉBITO",
        "BANCO DO BRASIL",
        "Exemplo de transporte",
    ],
    [
        "10/05/2026",
        "MAI",
        "2026",
        "DESPESA",
        "EDUCAÇÃO",
        "ESCOLA",
        "Mensalidade escolar",
        "1479,20",
        "1479,20",
        "PAGO",
        "PIX",
        "BANCO DO BRASIL",
        "Exemplo de educação",
    ],
]


LISTAS = {
    "A": ["MESES", "JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"],
    "B": ["TIPOS", "RECEITA", "DESPESA", "INVESTIMENTO", "TRANSFERÊNCIA", "DÍVIDA"],
    "C": [
        "CATEGORIAS",
        "SALÁRIO",
        "PESSOAIS",
        "CASA",
        "ALIMENTAÇÃO",
        "SAÚDE",
        "EDUCAÇÃO",
        "TRANSPORTE",
        "COMUNICAÇÃO",
        "LAZER",
        "OUTROS",
        "INVESTIMENTOS",
        "DÍVIDAS",
    ],
    "D": ["SITUACOES", "PAGO", "PENDENTE", "PREVISTO", "RECEBIDO", "CANCELADO"],
    "E": ["FORMAS_PAGAMENTO", "PIX", "CARTÃO", "DÉBITO", "DINHEIRO", "BOLETO", "CONTA", "TRANSFERÊNCIA"],
    "F": [
        "CONTAS",
        "BANCO DO BRASIL",
        "CAIXA",
        "NUBANK",
        "PAGBANK",
        "HIPERCARD",
        "PICPAY",
        "COFRE",
        "EM MÃOS",
        "OUTROS",
    ],
}


def extrair_id_planilha(link_ou_id: str) -> str:
    texto = link_ou_id.strip()

    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", texto)
    if match:
        return match.group(1)

    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", texto):
        return texto

    raise ValueError("Não foi possível identificar o ID da planilha.")


def autenticar() -> gspread.Client:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "credentials.json não encontrado. Coloque o arquivo na pasta SISTEMA FINANCEIRO."
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


def obter_ou_criar_aba(planilha, nome: str, linhas: int = 1000, colunas: int = 20):
    try:
        return planilha.worksheet(nome)
    except gspread.WorksheetNotFound:
        return planilha.add_worksheet(title=nome, rows=linhas, cols=colunas)


def coluna_para_indice(coluna: str) -> int:
    total = 0
    for char in coluna:
        total = total * 26 + (ord(char.upper()) - ord("A") + 1)
    return total - 1


def configurar_validacoes(planilha, aba_base, aba_listas):
    sheet_id = aba_base.id

    regras = [
        # MES - coluna B
        {
            "coluna_inicio": "B",
            "coluna_fim": "B",
            "formula": "=LISTAS_FINANCEIRO!$A$2:$A$13",
        },
        # TIPO - coluna D
        {
            "coluna_inicio": "D",
            "coluna_fim": "D",
            "formula": "=LISTAS_FINANCEIRO!$B$2:$B$6",
        },
        # CATEGORIA - coluna E
        {
            "coluna_inicio": "E",
            "coluna_fim": "E",
            "formula": "=LISTAS_FINANCEIRO!$C$2:$C$14",
        },
        # SITUACAO - coluna J
        {
            "coluna_inicio": "J",
            "coluna_fim": "J",
            "formula": "=LISTAS_FINANCEIRO!$D$2:$D$6",
        },
        # FORMA_PAGAMENTO - coluna K
        {
            "coluna_inicio": "K",
            "coluna_fim": "K",
            "formula": "=LISTAS_FINANCEIRO!$E$2:$E$8",
        },
        # CONTA - coluna L
        {
            "coluna_inicio": "L",
            "coluna_fim": "L",
            "formula": "=LISTAS_FINANCEIRO!$F$2:$F$10",
        },
    ]

    requests = []

    for regra in regras:
        start_col = coluna_para_indice(regra["coluna_inicio"])
        end_col = coluna_para_indice(regra["coluna_fim"]) + 1

        requests.append(
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": 1000,
                        "startColumnIndex": start_col,
                        "endColumnIndex": end_col,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_RANGE",
                            "values": [
                                {
                                    "userEnteredValue": regra["formula"]
                                }
                            ],
                        },
                        "showCustomUi": True,
                        "strict": False,
                    },
                }
            }
        )

    planilha.batch_update({"requests": requests})


def formatar_abas(planilha, aba_base, aba_listas):
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": aba_base.id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(CABECALHOS_BASE),
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.06, "green": 0.18, "blue": 0.35},
                        "horizontalAlignment": "CENTER",
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
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
                    "sheetId": aba_base.id,
                    "gridProperties": {
                        "frozenRowCount": 1
                    },
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": aba_base.id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": len(CABECALHOS_BASE),
                }
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": aba_listas.id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.06, "green": 0.18, "blue": 0.35},
                        "horizontalAlignment": "CENTER",
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "bold": True,
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": aba_listas.id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 6,
                }
            }
        },
    ]

    planilha.batch_update({"requests": requests})


def main():
    spreadsheet_id = extrair_id_planilha(LINK_PLANILHA)

    cliente = autenticar()
    planilha = cliente.open_by_key(spreadsheet_id)

    aba_base = obter_ou_criar_aba(planilha, "BASE_LANCAMENTOS", linhas=1000, colunas=20)
    aba_listas = obter_ou_criar_aba(planilha, "LISTAS_FINANCEIRO", linhas=100, colunas=10)

    aba_base.clear()
    aba_listas.clear()

    aba_base.update(
        "A1:M6",
        [CABECALHOS_BASE] + EXEMPLOS_BASE,
    )

    for coluna, valores in LISTAS.items():
        aba_listas.update(
            f"{coluna}1:{coluna}{len(valores)}",
            [[valor] for valor in valores],
        )

    configurar_validacoes(planilha, aba_base, aba_listas)
    formatar_abas(planilha, aba_base, aba_listas)

    print("Abas criadas/atualizadas com sucesso!")
    print("Planilha:", planilha.url)
    print("Aba BASE_LANCAMENTOS criada com cabeçalhos, exemplos e listas suspensas.")


if __name__ == "__main__":
    main()