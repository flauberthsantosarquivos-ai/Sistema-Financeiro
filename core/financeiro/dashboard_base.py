from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from core.financeiro.configuracao_sistema import obter_configuracao_sistema


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH = Path("token_financeiro_sheets.json")

NOME_ABA_BASE = "BASE_LANCAMENTOS"

MESES_VALIDOS = {
    "JAN": "Janeiro",
    "FEV": "Fevereiro",
    "MAR": "Março",
    "ABR": "Abril",
    "MAI": "Maio",
    "JUN": "Junho",
    "JUL": "Julho",
    "AGO": "Agosto",
    "SET": "Setembro",
    "OUT": "Outubro",
    "NOV": "Novembro",
    "DEZ": "Dezembro",
}

ORDEM_MESES = [
    "JAN",
    "FEV",
    "MAR",
    "ABR",
    "MAI",
    "JUN",
    "JUL",
    "AGO",
    "SET",
    "OUT",
    "NOV",
    "DEZ",
]

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
    "DATA_BANCO",
]


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


def extrair_id_planilha(link_ou_id: str) -> str:
    texto = (link_ou_id or "").strip()

    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", texto)

    if match:
        return match.group(1)

    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", texto):
        return texto

    raise ValueError("Não foi possível identificar o ID da planilha Google.")


def para_float(valor: Any) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")

    negativo_parenteses = texto.startswith("(") and texto.endswith(")")

    texto = texto.replace("(", "").replace(")", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    texto = re.sub(r"[^0-9\.-]", "", texto)

    if texto in {"", "-", ".", "-."}:
        return 0.0

    try:
        numero = float(texto)
    except ValueError:
        return 0.0

    if negativo_parenteses:
        numero = -abs(numero)

    return numero


def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def normalizar_texto(valor: Any) -> str:
    return str(valor or "").strip().upper()


def ler_base_lancamentos() -> list[dict[str, Any]]:
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    if not link_planilha:
        raise ValueError("Nenhuma planilha vinculada encontrada nas configurações.")

    spreadsheet_id = extrair_id_planilha(link_planilha)

    cliente = autenticar_sheets()
    planilha = cliente.open_by_key(spreadsheet_id)

    try:
        aba = planilha.worksheet(NOME_ABA_BASE)
    except gspread.WorksheetNotFound:
        raise ValueError("A aba BASE_LANCAMENTOS não foi encontrada na planilha vinculada.")

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


def filtrar_por_periodo(
    registros: list[dict[str, Any]],
    periodo_tipo: str,
    mes_unico: str,
    mes_inicio: str,
    mes_fim: str,
    ano: str,
) -> list[dict[str, Any]]:
    registros_filtrados = []

    ano = str(ano or "").strip()

    for item in registros:
        item_mes = normalizar_texto(item.get("MES"))
        item_ano = str(item.get("ANO", "")).strip()

        if ano and item_ano and item_ano != ano:
            continue

        if periodo_tipo == "mes_unico":
            if item_mes != mes_unico:
                continue

        elif periodo_tipo == "intervalo":
            if mes_inicio in ORDEM_MESES and mes_fim in ORDEM_MESES and item_mes in ORDEM_MESES:
                idx_inicio = ORDEM_MESES.index(mes_inicio)
                idx_fim = ORDEM_MESES.index(mes_fim)

                if idx_inicio > idx_fim:
                    idx_inicio, idx_fim = idx_fim, idx_inicio

                idx_item = ORDEM_MESES.index(item_mes)

                if not (idx_inicio <= idx_item <= idx_fim):
                    continue

        registros_filtrados.append(item)

    return registros_filtrados


def montar_periodo_descricao(
    periodo_tipo: str,
    mes_unico: str,
    mes_inicio: str,
    mes_fim: str,
    ano: str,
) -> str:
    if periodo_tipo == "mes_unico":
        return f"{MESES_VALIDOS.get(mes_unico, mes_unico)} / {ano}"

    if periodo_tipo == "intervalo":
        return (
            f"{MESES_VALIDOS.get(mes_inicio, mes_inicio)} "
            f"a {MESES_VALIDOS.get(mes_fim, mes_fim)} / {ano}"
        )

    return f"Todos os meses / {ano}"


def gerar_diagnostico(cards: dict[str, Any], ranking_categorias: list[dict[str, Any]], por_origem: list[dict[str, Any]]) -> dict[str, list[str]]:
    alertas = []
    pontos_positivos = []
    sugestoes = []

    receita_total = cards["receita_total"]
    despesa_total = cards["despesa_total"]
    saldo_realizado = cards["saldo_realizado"]
    comprometimento = cards["percentual_comprometimento"]

    if receita_total <= 0:
        alertas.append("Não há receita registrada no período. O diagnóstico fica limitado até que receitas sejam lançadas.")
    else:
        if comprometimento <= 50:
            pontos_positivos.append("O comprometimento da receita está em nível saudável, abaixo de 50%.")
        elif comprometimento <= 70:
            alertas.append("As despesas já comprometem mais de 50% da receita. Vale acompanhar os gastos variáveis.")
        else:
            alertas.append("As despesas comprometem mais de 70% da receita. O orçamento exige atenção.")

    if saldo_realizado > 0:
        pontos_positivos.append("O período apresenta saldo positivo considerando receitas e despesas realizadas.")
    elif saldo_realizado < 0:
        alertas.append("O período apresenta saldo realizado negativo. É recomendável revisar despesas não essenciais.")

    if ranking_categorias:
        maior = ranking_categorias[0]

        if maior["valor"] > 0:
            sugestoes.append(
                f"A categoria de maior impacto é {maior['categoria']}, com {maior['valor_fmt']}. "
                "Avalie se esse valor está coerente com o planejamento do mês."
            )

    origem_importacao = next(
        (item for item in por_origem if item["origem"] == "IMPORTACAO_EXTRATO"),
        None,
    )

    if origem_importacao and origem_importacao["quantidade"] > 0:
        pontos_positivos.append(
            f"O sistema já possui {origem_importacao['quantidade']} lançamento(s) importado(s) de extrato, "
            "o que melhora a precisão dos valores realizados."
        )
    else:
        sugestoes.append(
            "Importar o extrato bancário ajuda a comparar o que foi planejado com o que realmente aconteceu."
        )

    if not sugestoes:
        sugestoes.append("Mantenha o acompanhamento semanal para evitar acúmulo de despesas não previstas.")

    return {
        "alertas": alertas,
        "pontos_positivos": pontos_positivos,
        "sugestoes": sugestoes,
    }


def processar_dashboard_base(
    periodo_tipo: str = "todos",
    mes_unico: str = "MAI",
    mes_inicio: str = "JAN",
    mes_fim: str = "DEZ",
    ano: str | int = "2026",
) -> dict[str, Any]:
    registros = ler_base_lancamentos()

    registros = filtrar_por_periodo(
        registros=registros,
        periodo_tipo=periodo_tipo,
        mes_unico=mes_unico,
        mes_inicio=mes_inicio,
        mes_fim=mes_fim,
        ano=str(ano),
    )

    receita_prevista = 0.0
    receita_realizada = 0.0
    despesa_prevista = 0.0
    despesa_realizada = 0.0

    por_categoria = {}
    por_mes = {}
    por_origem = {}
    por_situacao = {}

    linhas = []

    for item in registros:
        mes = normalizar_texto(item.get("MES"))
        ano_item = str(item.get("ANO", "")).strip()
        tipo = normalizar_texto(item.get("TIPO"))
        categoria = normalizar_texto(item.get("CATEGORIA")) or "SEM CATEGORIA"
        subcategoria = normalizar_texto(item.get("SUBCATEGORIA"))
        descricao = str(item.get("DESCRICAO", "")).strip()
        situacao = normalizar_texto(item.get("SITUACAO")) or "SEM SITUAÇÃO"
        origem = normalizar_texto(item.get("ORIGEM")) or "SEM ORIGEM"
        conta = normalizar_texto(item.get("CONTA"))

        valor_previsto = abs(para_float(item.get("VALOR_PREVISTO")))
        valor_realizado = abs(para_float(item.get("VALOR_REALIZADO")))

        valor_base = valor_realizado if valor_realizado > 0 else valor_previsto

        if tipo == "RECEITA":
            receita_prevista += valor_previsto
            receita_realizada += valor_realizado
        elif tipo == "DESPESA":
            despesa_prevista += valor_previsto
            despesa_realizada += valor_realizado

            if categoria not in por_categoria:
                por_categoria[categoria] = 0.0

            por_categoria[categoria] += valor_base

        if mes not in por_mes:
            por_mes[mes] = {
                "mes": mes,
                "mes_nome": MESES_VALIDOS.get(mes, mes),
                "receita_prevista": 0.0,
                "receita_realizada": 0.0,
                "despesa_prevista": 0.0,
                "despesa_realizada": 0.0,
            }

        if tipo == "RECEITA":
            por_mes[mes]["receita_prevista"] += valor_previsto
            por_mes[mes]["receita_realizada"] += valor_realizado
        elif tipo == "DESPESA":
            por_mes[mes]["despesa_prevista"] += valor_previsto
            por_mes[mes]["despesa_realizada"] += valor_realizado

        if origem not in por_origem:
            por_origem[origem] = {
                "origem": origem,
                "quantidade": 0,
                "valor": 0.0,
            }

        por_origem[origem]["quantidade"] += 1
        por_origem[origem]["valor"] += valor_base

        if situacao not in por_situacao:
            por_situacao[situacao] = {
                "situacao": situacao,
                "quantidade": 0,
                "valor": 0.0,
            }

        por_situacao[situacao]["quantidade"] += 1
        por_situacao[situacao]["valor"] += valor_base

        linhas.append(
            {
                "data": item.get("DATA", ""),
                "data_banco": item.get("DATA_BANCO", ""),
                "mes": mes,
                "ano": ano_item,
                "tipo": tipo,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "descricao": descricao,
                "valor_previsto": valor_previsto,
                "valor_realizado": valor_realizado,
                "valor_previsto_fmt": formatar_moeda(valor_previsto),
                "valor_realizado_fmt": formatar_moeda(valor_realizado),
                "situacao": situacao,
                "origem": origem,
                "conta": conta,
            }
        )

    saldo_previsto = receita_prevista - despesa_prevista
    saldo_realizado = receita_realizada - despesa_realizada

    receita_total = receita_realizada if receita_realizada > 0 else receita_prevista
    despesa_total = despesa_realizada if despesa_realizada > 0 else despesa_prevista

    percentual_comprometimento = 0.0
    if receita_total > 0:
        percentual_comprometimento = (despesa_total / receita_total) * 100

    ranking_categorias = [
        {
            "categoria": categoria,
            "valor": valor,
            "valor_fmt": formatar_moeda(valor),
        }
        for categoria, valor in sorted(
            por_categoria.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    maior_valor_categoria = ranking_categorias[0]["valor"] if ranking_categorias else 1

    for item in ranking_categorias:
        if maior_valor_categoria > 0:
            item["percentual_visual"] = (item["valor"] / maior_valor_categoria) * 100
        else:
            item["percentual_visual"] = 0

    resumo_mensal = []

    for mes in ORDEM_MESES:
        if mes not in por_mes:
            continue

        item = por_mes[mes]
        item["receita_prevista_fmt"] = formatar_moeda(item["receita_prevista"])
        item["receita_realizada_fmt"] = formatar_moeda(item["receita_realizada"])
        item["despesa_prevista_fmt"] = formatar_moeda(item["despesa_prevista"])
        item["despesa_realizada_fmt"] = formatar_moeda(item["despesa_realizada"])
        item["saldo_previsto"] = item["receita_prevista"] - item["despesa_prevista"]
        item["saldo_realizado"] = item["receita_realizada"] - item["despesa_realizada"]
        item["saldo_previsto_fmt"] = formatar_moeda(item["saldo_previsto"])
        item["saldo_realizado_fmt"] = formatar_moeda(item["saldo_realizado"])

        resumo_mensal.append(item)

    lista_origem = list(por_origem.values())

    for item in lista_origem:
        item["valor_fmt"] = formatar_moeda(item["valor"])

    lista_origem.sort(key=lambda x: x["valor"], reverse=True)

    lista_situacao = list(por_situacao.values())

    for item in lista_situacao:
        item["valor_fmt"] = formatar_moeda(item["valor"])

    lista_situacao.sort(key=lambda x: x["valor"], reverse=True)

    cards = {
        "receita_prevista": receita_prevista,
        "receita_realizada": receita_realizada,
        "despesa_prevista": despesa_prevista,
        "despesa_realizada": despesa_realizada,
        "saldo_previsto": saldo_previsto,
        "saldo_realizado": saldo_realizado,
        "receita_total": receita_total,
        "despesa_total": despesa_total,
        "percentual_comprometimento": percentual_comprometimento,
        "receita_prevista_fmt": formatar_moeda(receita_prevista),
        "receita_realizada_fmt": formatar_moeda(receita_realizada),
        "despesa_prevista_fmt": formatar_moeda(despesa_prevista),
        "despesa_realizada_fmt": formatar_moeda(despesa_realizada),
        "saldo_previsto_fmt": formatar_moeda(saldo_previsto),
        "saldo_realizado_fmt": formatar_moeda(saldo_realizado),
        "percentual_comprometimento_fmt": f"{percentual_comprometimento:.2f}%",
        "quantidade_lancamentos": len(registros),
    }

    diagnostico = gerar_diagnostico(
        cards=cards,
        ranking_categorias=ranking_categorias,
        por_origem=lista_origem,
    )

    config = obter_configuracao_sistema()

    return {
        "fonte": "BASE_LANCAMENTOS",
        "planilha_google": config.get("planilha_google", ""),
        "periodo_descricao": montar_periodo_descricao(
            periodo_tipo=periodo_tipo,
            mes_unico=mes_unico,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            ano=str(ano),
        ),
        "cards": cards,
        "ranking_categorias": ranking_categorias,
        "resumo_mensal": resumo_mensal,
        "por_origem": lista_origem,
        "por_situacao": lista_situacao,
        "lancamentos": linhas,
        "diagnostico": diagnostico,
    }