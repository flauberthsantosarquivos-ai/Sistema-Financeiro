from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import (
    filtrar_por_periodo,
    formatar_moeda,
    ler_base_lancamentos,
    para_float,
)
from core.financeiro.orcamento_google import ler_orcamento_mensal


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


MESES_OPCOES = [
    ("JAN", "Janeiro"),
    ("FEV", "Fevereiro"),
    ("MAR", "Março"),
    ("ABR", "Abril"),
    ("MAI", "Maio"),
    ("JUN", "Junho"),
    ("JUL", "Julho"),
    ("AGO", "Agosto"),
    ("SET", "Setembro"),
    ("OUT", "Outubro"),
    ("NOV", "Novembro"),
    ("DEZ", "Dezembro"),
]

MESES_MAPA = {
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

ORDEM_MESES = [sigla for sigla, _ in MESES_OPCOES]


CORES_CATEGORIAS = {
    "ALIMENTAÇÃO": {"cor": "#047857", "fundo": "#ecfdf5", "borda": "#bbf7d0"},
    "MORADIA": {"cor": "#1d4ed8", "fundo": "#eff6ff", "borda": "#bfdbfe"},
    "CASA": {"cor": "#2563eb", "fundo": "#eff6ff", "borda": "#bfdbfe"},
    "TRANSPORTE": {"cor": "#ea580c", "fundo": "#fff7ed", "borda": "#fed7aa"},
    "SAÚDE": {"cor": "#dc2626", "fundo": "#fef2f2", "borda": "#fecaca"},
    "EDUCAÇÃO": {"cor": "#7c3aed", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "COMUNICAÇÃO": {"cor": "#0891b2", "fundo": "#ecfeff", "borda": "#a5f3fc"},
    "INVESTIMENTO": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "INVESTIMENTOS": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "RESERVA": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "POUPANÇA": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "RENDA FIXA": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "RENDA VARIÁVEL": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "TESOURO": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "CDB": {"cor": "#6d28d9", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    "TRANSFERÊNCIA": {"cor": "#64748b", "fundo": "#f8fafc", "borda": "#cbd5e1"},
    "TRANSFERÊNCIA VIA PIX": {"cor": "#64748b", "fundo": "#f8fafc", "borda": "#cbd5e1"},
    "CONTAS PRÓPRIAS": {"cor": "#64748b", "fundo": "#f8fafc", "borda": "#cbd5e1"},
    "MOVIMENTAÇÃO ENTRE CONTAS": {"cor": "#64748b", "fundo": "#f8fafc", "borda": "#cbd5e1"},
    "OUTROS": {"cor": "#64748b", "fundo": "#f8fafc", "borda": "#cbd5e1"},
    "SEM CATEGORIA": {"cor": "#64748b", "fundo": "#f8fafc", "borda": "#cbd5e1"},
}


PALETA_PADRAO = [
    {"cor": "#047857", "fundo": "#ecfdf5", "borda": "#bbf7d0"},
    {"cor": "#1d4ed8", "fundo": "#eff6ff", "borda": "#bfdbfe"},
    {"cor": "#ea580c", "fundo": "#fff7ed", "borda": "#fed7aa"},
    {"cor": "#7c3aed", "fundo": "#f5f3ff", "borda": "#ddd6fe"},
    {"cor": "#dc2626", "fundo": "#fef2f2", "borda": "#fecaca"},
    {"cor": "#0891b2", "fundo": "#ecfeff", "borda": "#a5f3fc"},
    {"cor": "#b45309", "fundo": "#fffbeb", "borda": "#fde68a"},
    {"cor": "#64748b", "fundo": "#f8fafc", "borda": "#cbd5e1"},
]


CATEGORIAS_INVESTIMENTO = {
    "INVESTIMENTO",
    "INVESTIMENTOS",
    "INVESTIMENTOS / RESERVA",
    "RESERVA",
    "RESERVA FINANCEIRA",
    "RESERVA DE EMERGÊNCIA",
    "POUPANÇA",
    "POUPANCA",
    "APLICAÇÃO",
    "APLICACAO",
    "APLICAÇÕES",
    "APLICACOES",
    "RENDA FIXA",
    "RENDA VARIÁVEL",
    "RENDA VARIAVEL",
    "TESOURO",
    "TESOURO DIRETO",
    "CDB",
    "LCI",
    "LCA",
    "PREVIDÊNCIA",
    "PREVIDENCIA",
    "AÇÕES",
    "ACOES",
    "FUNDOS",
    "CRIPTO",
    "CRIPTOATIVOS",
}

CATEGORIAS_MOVIMENTACAO_NEUTRA = {
    "TRANSFERÊNCIA",
    "TRANSFERENCIA",
    "TRANSFERÊNCIAS",
    "TRANSFERENCIAS",
    "CONTAS PRÓPRIAS",
    "CONTAS PROPRIAS",
    "ENTRE CONTAS",
    "MOVIMENTAÇÃO ENTRE CONTAS",
    "MOVIMENTACAO ENTRE CONTAS",
    "MOVIMENTAÇÃO",
    "MOVIMENTACAO",
}

CATEGORIAS_PENDENTES = {
    "",
    "A CLASSIFICAR",
    "SEM CATEGORIA",
    "NÃO CLASSIFICADO",
    "NAO CLASSIFICADO",
}


def normalizar(valor) -> str:
    texto = str(valor or "").strip().upper()

    if texto == "TRANSFERENCIA":
        return "TRANSFERÊNCIA"

    return texto


def contem_termo(texto: str, termos: set[str]) -> bool:
    texto_normalizado = normalizar(texto)

    for termo in termos:
        termo_normalizado = normalizar(termo)

        if termo_normalizado and termo_normalizado in texto_normalizado:
            return True

    return False


def classificar_gerencialmente(item: dict) -> str:
    tipo = normalizar(item.get("TIPO"))
    categoria = normalizar(item.get("CATEGORIA"))
    subcategoria = normalizar(item.get("SUBCATEGORIA"))
    descricao = normalizar(item.get("DESCRICAO"))

    texto_classificacao = " ".join(
        [
            tipo,
            categoria,
            subcategoria,
            descricao,
        ]
    )

    if tipo == "RECEITA":
        return "RECEITA"

    if tipo == "DESPESA":
        return "DESPESA"

    if tipo == "INVESTIMENTO":
        return "INVESTIMENTO"

    if contem_termo(texto_classificacao, CATEGORIAS_INVESTIMENTO):
        return "INVESTIMENTO"

    if tipo == "TRANSFERÊNCIA":
        if categoria in CATEGORIAS_PENDENTES:
            return "A_CLASSIFICAR"

        if contem_termo(texto_classificacao, CATEGORIAS_MOVIMENTACAO_NEUTRA):
            return "TRANSFERÊNCIA"

        return "DESPESA"

    return tipo


def valor_previsto(item: dict) -> float:
    return abs(para_float(item.get("VALOR_PREVISTO")))


def valor_realizado(item: dict) -> float:
    return abs(para_float(item.get("VALOR_REALIZADO")))


def valor_base_lancamento(item: dict) -> float:
    realizado = valor_realizado(item)
    previsto = valor_previsto(item)

    if realizado > 0:
        return realizado

    return previsto


def valor_previsto_orcamento(item: dict) -> float:
    if "VALOR_PREVISTO_NUM" in item:
        return abs(float(item.get("VALOR_PREVISTO_NUM", 0) or 0))

    return abs(para_float(item.get("VALOR_PREVISTO")))


def montar_detalhe_lancamento(
    data: str,
    descricao: str,
    categoria: str,
    subcategoria: str,
    situacao: str,
    tipo: str,
    valor: float,
) -> dict:
    return {
        "data": data,
        "descricao": descricao,
        "tipo": tipo,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "situacao": situacao,
        "valor": valor,
        "valor_fmt": formatar_moeda(valor),
    }


def ordenar_lancamentos_por_valor(lancamentos: list[dict]) -> list[dict]:
    return sorted(
        lancamentos,
        key=lambda item: item.get("valor", 0),
        reverse=True,
    )


def obter_estilo_categoria(categoria: str, indice: int) -> dict:
    categoria_normalizada = normalizar(categoria)

    for chave, estilo in CORES_CATEGORIAS.items():
        if chave in categoria_normalizada or categoria_normalizada in chave:
            return estilo

    return PALETA_PADRAO[indice % len(PALETA_PADRAO)]


def extrair_mes(item: dict) -> str:
    mes = normalizar(item.get("MES"))

    if mes in MESES_MAPA:
        return mes

    data_lancamento = str(item.get("DATA", "")).strip()

    if "/" in data_lancamento:
        partes = data_lancamento.split("/")

        if len(partes) >= 2:
            try:
                numero_mes = int(partes[1])

                if 1 <= numero_mes <= 12:
                    return ORDEM_MESES[numero_mes - 1]
            except Exception:
                pass

    return ""


def filtrar_orcamento_por_periodo(
    registros_orcamento: list[dict],
    periodo_tipo: str,
    mes_unico: str,
    mes_inicio: str,
    mes_fim: str,
    ano: str,
) -> list[dict]:
    periodo_tipo = normalizar(periodo_tipo)
    mes_unico = normalizar(mes_unico)
    mes_inicio = normalizar(mes_inicio)
    mes_fim = normalizar(mes_fim)
    ano = str(ano or "").strip()

    filtrados = []

    indice_inicio = 0
    indice_fim = len(ORDEM_MESES) - 1

    if periodo_tipo == "MES_UNICO" and mes_unico in ORDEM_MESES:
        indice_inicio = ORDEM_MESES.index(mes_unico)
        indice_fim = indice_inicio

    elif periodo_tipo == "INTERVALO":
        if mes_inicio in ORDEM_MESES:
            indice_inicio = ORDEM_MESES.index(mes_inicio)

        if mes_fim in ORDEM_MESES:
            indice_fim = ORDEM_MESES.index(mes_fim)

        if indice_inicio > indice_fim:
            indice_inicio, indice_fim = indice_fim, indice_inicio

    for item in registros_orcamento:
        item_ano = str(item.get("ANO", "")).strip()
        item_mes = normalizar(item.get("MES"))

        if ano and item_ano != ano:
            continue

        if item_mes not in ORDEM_MESES:
            continue

        indice_mes = ORDEM_MESES.index(item_mes)

        if indice_inicio <= indice_mes <= indice_fim:
            filtrados.append(item)

    return filtrados


def calcular_totais_previstos_orcamento(registros_orcamento: list[dict]) -> dict:
    total_receitas = 0.0
    total_despesas = 0.0
    total_investimentos = 0.0
    total_transferencias = 0.0

    for item in registros_orcamento:
        classificacao = classificar_gerencialmente(item)
        valor = valor_previsto_orcamento(item)

        if valor <= 0:
            continue

        if classificacao == "RECEITA":
            total_receitas += valor
        elif classificacao == "DESPESA":
            total_despesas += valor
        elif classificacao == "INVESTIMENTO":
            total_investimentos += valor
        elif classificacao == "TRANSFERÊNCIA":
            total_transferencias += valor

    return {
        "receitas": total_receitas,
        "despesas": total_despesas,
        "investimentos": total_investimentos,
        "transferencias": total_transferencias,
    }


def calcular_evolucao_mensal(registros: list[dict]) -> dict:
    meses = []

    for sigla, nome in MESES_OPCOES:
        meses.append(
            {
                "mes": sigla,
                "nome": nome,
                "receitas": 0.0,
                "despesas": 0.0,
                "investimentos": 0.0,
                "transferencias": 0.0,
                "saldo": 0.0,
                "disponivel_apos_investimentos": 0.0,
                "comprometimento": 0.0,
                "qtd_lancamentos": 0,
            }
        )

    indice_por_mes = {
        item["mes"]: indice
        for indice, item in enumerate(meses)
    }

    for item in registros:
        classificacao = classificar_gerencialmente(item)
        mes = extrair_mes(item)
        valor = valor_base_lancamento(item)

        if not mes or mes not in indice_por_mes or valor <= 0:
            continue

        indice = indice_por_mes[mes]

        if classificacao == "RECEITA":
            meses[indice]["receitas"] += valor
            meses[indice]["qtd_lancamentos"] += 1

        elif classificacao == "DESPESA":
            meses[indice]["despesas"] += valor
            meses[indice]["qtd_lancamentos"] += 1

        elif classificacao == "INVESTIMENTO":
            meses[indice]["investimentos"] += valor
            meses[indice]["qtd_lancamentos"] += 1

        elif classificacao == "TRANSFERÊNCIA":
            meses[indice]["transferencias"] += valor
            meses[indice]["qtd_lancamentos"] += 1

    maior_valor = 0.0

    for item in meses:
        item["saldo"] = item["receitas"] - item["despesas"]
        item["disponivel_apos_investimentos"] = item["saldo"] - item["investimentos"]

        if item["receitas"] > 0:
            item["comprometimento"] = (item["despesas"] / item["receitas"]) * 100

        maior_valor = max(
            maior_valor,
            item["receitas"],
            item["despesas"],
            item["investimentos"],
            abs(item["saldo"]),
            abs(item["disponivel_apos_investimentos"]),
        )

    meses_formatados = []

    for item in meses:
        receitas_pct = (item["receitas"] / maior_valor * 100) if maior_valor > 0 else 0
        despesas_pct = (item["despesas"] / maior_valor * 100) if maior_valor > 0 else 0
        investimentos_pct = (item["investimentos"] / maior_valor * 100) if maior_valor > 0 else 0
        saldo_pct = (abs(item["saldo"]) / maior_valor * 100) if maior_valor > 0 else 0
        disponivel_pct = (
            abs(item["disponivel_apos_investimentos"]) / maior_valor * 100
            if maior_valor > 0
            else 0
        )

        meses_formatados.append(
            {
                **item,
                "receitas_fmt": formatar_moeda(item["receitas"]),
                "despesas_fmt": formatar_moeda(item["despesas"]),
                "investimentos_fmt": formatar_moeda(item["investimentos"]),
                "transferencias_fmt": formatar_moeda(item["transferencias"]),
                "saldo_fmt": formatar_moeda(item["saldo"]),
                "disponivel_apos_investimentos_fmt": formatar_moeda(item["disponivel_apos_investimentos"]),
                "comprometimento_fmt": f"{item['comprometimento']:.1f}".replace(".", ",") + "%",
                "receitas_pct": receitas_pct,
                "despesas_pct": despesas_pct,
                "investimentos_pct": investimentos_pct,
                "saldo_pct": saldo_pct,
                "disponivel_pct": disponivel_pct,
            }
        )

    total_receitas = sum(item["receitas"] for item in meses)
    total_despesas = sum(item["despesas"] for item in meses)
    total_investimentos = sum(item["investimentos"] for item in meses)
    saldo_total = total_receitas - total_despesas
    disponivel_total = saldo_total - total_investimentos

    melhor_mes = None
    pior_mes = None

    meses_com_movimento = [
        item for item in meses_formatados
        if item["receitas"] > 0
        or item["despesas"] > 0
        or item["investimentos"] > 0
    ]

    if meses_com_movimento:
        melhor_mes = max(meses_com_movimento, key=lambda item: item["saldo"])
        pior_mes = min(meses_com_movimento, key=lambda item: item["saldo"])

    return {
        "meses": meses_formatados,
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "total_investimentos": total_investimentos,
        "saldo_total": saldo_total,
        "disponivel_total": disponivel_total,
        "total_receitas_fmt": formatar_moeda(total_receitas),
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "total_investimentos_fmt": formatar_moeda(total_investimentos),
        "saldo_total_fmt": formatar_moeda(saldo_total),
        "disponivel_total_fmt": formatar_moeda(disponivel_total),
        "melhor_mes": melhor_mes,
        "pior_mes": pior_mes,
    }


def calcular_orcamento_por_categoria(
    registros_realizados: list[dict],
    registros_orcamento: list[dict],
) -> dict:
    categorias = {}

    for item in registros_orcamento:
        classificacao = classificar_gerencialmente(item)

        if classificacao != "DESPESA":
            continue

        categoria = str(item.get("CATEGORIA", "")).strip().upper() or "SEM CATEGORIA"
        valor = valor_previsto_orcamento(item)

        if valor <= 0:
            continue

        categorias.setdefault(
            categoria,
            {
                "previsto": 0.0,
                "realizado": 0.0,
                "qtd_previstos": 0,
                "qtd_realizados": 0,
            },
        )

        categorias[categoria]["previsto"] += valor
        categorias[categoria]["qtd_previstos"] += 1

    for item in registros_realizados:
        classificacao = classificar_gerencialmente(item)

        if classificacao != "DESPESA":
            continue

        categoria = str(item.get("CATEGORIA", "")).strip().upper() or "SEM CATEGORIA"
        realizado = valor_realizado(item)

        if realizado <= 0:
            realizado = valor_base_lancamento(item)

        if realizado <= 0:
            continue

        categorias.setdefault(
            categoria,
            {
                "previsto": 0.0,
                "realizado": 0.0,
                "qtd_previstos": 0,
                "qtd_realizados": 0,
            },
        )

        categorias[categoria]["realizado"] += realizado
        categorias[categoria]["qtd_realizados"] += 1

    lista = []
    total_previsto = 0.0
    total_realizado = 0.0

    for indice, (categoria, valores) in enumerate(categorias.items()):
        previsto = valores["previsto"]
        realizado = valores["realizado"]
        diferenca = realizado - previsto

        execucao = 0.0
        if previsto > 0:
            execucao = (realizado / previsto) * 100

        if previsto <= 0 and realizado > 0:
            status = "Sem previsto"
            status_classe = "sem-previsto"
        elif execucao <= 100:
            status = "Dentro do previsto"
            status_classe = "dentro"
        elif execucao <= 115:
            status = "Atenção"
            status_classe = "atencao"
        else:
            status = "Acima do previsto"
            status_classe = "acima"

        estilo = obter_estilo_categoria(categoria, indice)

        total_previsto += previsto
        total_realizado += realizado

        lista.append(
            {
                "categoria": categoria,
                "previsto": previsto,
                "realizado": realizado,
                "diferenca": diferenca,
                "execucao": execucao,
                "previsto_fmt": formatar_moeda(previsto),
                "realizado_fmt": formatar_moeda(realizado),
                "diferenca_fmt": formatar_moeda(abs(diferenca)),
                "execucao_fmt": f"{execucao:.1f}".replace(".", ",") + "%" if previsto > 0 else "Sem previsto",
                "qtd_previstos": valores["qtd_previstos"],
                "qtd_realizados": valores["qtd_realizados"],
                "qtd_lancamentos": valores["qtd_realizados"],
                "status": status,
                "status_classe": status_classe,
                "cor": estilo["cor"],
                "cor_fundo": estilo["fundo"],
                "cor_borda": estilo["borda"],
            }
        )

    lista = sorted(
      lista,
      key=lambda item: (
        item["diferenca"] <= 0,
        -item["diferenca"] if item["diferenca"] > 0 else -item["realizado"],
    ),
  )

    diferenca_total = total_realizado - total_previsto

    execucao_total = 0.0
    if total_previsto > 0:
        execucao_total = (total_realizado / total_previsto) * 100

    return {
        "categorias": lista,
        "total_previsto": total_previsto,
        "total_realizado": total_realizado,
        "diferenca_total": diferenca_total,
        "execucao_total": execucao_total,
        "total_previsto_fmt": formatar_moeda(total_previsto),
        "total_realizado_fmt": formatar_moeda(total_realizado),
        "diferenca_total_fmt": formatar_moeda(abs(diferenca_total)),
        "execucao_total_fmt": f"{execucao_total:.1f}".replace(".", ",") + "%" if total_previsto > 0 else "Sem previsto",
    }


def preparar_analise(
    registros: list[dict],
    registros_ano: list[dict] | None = None,
    registros_orcamento: list[dict] | None = None,
) -> dict:
    registros_orcamento = registros_orcamento or []

    total_receitas = 0.0
    total_despesas = 0.0
    total_investimentos = 0.0
    total_transferencias = 0.0

    total_receitas_realizado = 0.0
    total_despesas_realizado = 0.0
    total_investimentos_realizado = 0.0

    qtd_receitas = 0
    qtd_despesas = 0
    qtd_investimentos = 0
    qtd_transferencias = 0
    qtd_a_classificar = 0

    despesas_por_categoria = {}
    despesas_por_categoria_subcategoria = {}
    investimentos_por_categoria = {}
    receitas_por_categoria = {}

    top_despesas = []
    lancamentos_receitas = []
    lancamentos_despesas = []
    lancamentos_investimentos = []

    for item in registros:
        classificacao = classificar_gerencialmente(item)
        tipo_original = normalizar(item.get("TIPO"))

        categoria = str(item.get("CATEGORIA", "")).strip() or "SEM CATEGORIA"
        subcategoria = str(item.get("SUBCATEGORIA", "")).strip() or "SEM SUBCATEGORIA"
        descricao = str(item.get("DESCRICAO", "")).strip()
        data = str(item.get("DATA", "")).strip()
        situacao = str(item.get("SITUACAO", "")).strip()

        realizado = valor_realizado(item)
        valor = valor_base_lancamento(item)

        if valor <= 0:
            continue

        detalhe = montar_detalhe_lancamento(
            data=data,
            descricao=descricao,
            categoria=categoria,
            subcategoria=subcategoria,
            situacao=situacao,
            tipo=tipo_original,
            valor=valor,
        )

        texto_classificacao = normalizar(
            " ".join(
                [
                    str(item.get("CATEGORIA", "")),
                    str(item.get("SUBCATEGORIA", "")),
                    str(item.get("DESCRICAO", "")),
                ]
            )
        )

        if "A CLASSIFICAR" in texto_classificacao or classificacao == "A_CLASSIFICAR":
            qtd_a_classificar += 1

        if classificacao == "RECEITA":
            total_receitas += valor
            total_receitas_realizado += realizado if realizado > 0 else valor

            qtd_receitas += 1
            receitas_por_categoria[categoria] = receitas_por_categoria.get(categoria, 0.0) + valor
            lancamentos_receitas.append(detalhe)

        elif classificacao == "DESPESA":
            total_despesas += valor
            total_despesas_realizado += realizado if realizado > 0 else valor

            qtd_despesas += 1
            despesas_por_categoria[categoria] = despesas_por_categoria.get(categoria, 0.0) + valor
            lancamentos_despesas.append(detalhe)

            despesas_por_categoria_subcategoria.setdefault(categoria, {})
            despesas_por_categoria_subcategoria[categoria].setdefault(
                subcategoria,
                {
                    "valor": 0.0,
                    "lancamentos": [],
                },
            )

            despesas_por_categoria_subcategoria[categoria][subcategoria]["valor"] += valor
            despesas_por_categoria_subcategoria[categoria][subcategoria]["lancamentos"].append(detalhe)

            top_despesas.append(detalhe)

        elif classificacao == "INVESTIMENTO":
            total_investimentos += valor
            total_investimentos_realizado += realizado if realizado > 0 else valor

            qtd_investimentos += 1
            investimentos_por_categoria[categoria] = investimentos_por_categoria.get(categoria, 0.0) + valor
            lancamentos_investimentos.append(detalhe)

        elif classificacao == "TRANSFERÊNCIA":
            total_transferencias += valor
            qtd_transferencias += 1

        elif tipo_original == "TRANSFERÊNCIA":
            total_transferencias += valor
            qtd_transferencias += 1

    totais_orcamento = calcular_totais_previstos_orcamento(registros_orcamento)

    total_receitas_previsto = totais_orcamento["receitas"]
    total_despesas_previsto = totais_orcamento["despesas"]
    total_investimentos_previsto = totais_orcamento["investimentos"]

    saldo = total_receitas - total_despesas
    disponivel_apos_investimentos = saldo - total_investimentos

    comprometimento = 0.0
    if total_receitas > 0:
        comprometimento = (total_despesas / total_receitas) * 100

    saldo_percentual_receita = 0.0
    if total_receitas > 0:
        saldo_percentual_receita = (saldo / total_receitas) * 100

    percentual_investimento_receita = 0.0
    if total_receitas > 0:
        percentual_investimento_receita = (total_investimentos / total_receitas) * 100

    disponivel_percentual_receita = 0.0
    if total_receitas > 0:
        disponivel_percentual_receita = (disponivel_apos_investimentos / total_receitas) * 100

    media_despesas = 0.0
    if qtd_despesas > 0:
        media_despesas = total_despesas / qtd_despesas

    diferenca_despesas = total_despesas_realizado - total_despesas_previsto

    percentual_execucao_despesas = 0.0
    if total_despesas_previsto > 0:
        percentual_execucao_despesas = (total_despesas_realizado / total_despesas_previsto) * 100

    diferenca_receitas = total_receitas_realizado - total_receitas_previsto

    percentual_execucao_receitas = 0.0
    if total_receitas_previsto > 0:
        percentual_execucao_receitas = (total_receitas_realizado / total_receitas_previsto) * 100

    diferenca_investimentos = total_investimentos_realizado - total_investimentos_previsto

    percentual_execucao_investimentos = 0.0
    if total_investimentos_previsto > 0:
        percentual_execucao_investimentos = (
            total_investimentos_realizado / total_investimentos_previsto
        ) * 100

    categorias_ordenadas = sorted(
        despesas_por_categoria.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    receitas_ordenadas = sorted(
        receitas_por_categoria.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    investimentos_ordenados = sorted(
        investimentos_por_categoria.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_despesas = sorted(
        top_despesas,
        key=lambda item: item["valor"],
        reverse=True,
    )[:10]

    maior_categoria = categorias_ordenadas[0][0] if categorias_ordenadas else "Sem despesas"
    maior_categoria_valor = categorias_ordenadas[0][1] if categorias_ordenadas else 0.0

    maior_despesa = top_despesas[0] if top_despesas else None

    despesas_por_categoria_lista = []

    for indice_categoria, (categoria, valor_categoria) in enumerate(categorias_ordenadas):
        percentual_categoria = (valor_categoria / total_despesas * 100) if total_despesas > 0 else 0
        estilo = obter_estilo_categoria(categoria, indice_categoria)

        subcategorias_raw = despesas_por_categoria_subcategoria.get(categoria, {})

        subcategorias_ordenadas = sorted(
            subcategorias_raw.items(),
            key=lambda item: item[1]["valor"],
            reverse=True,
        )

        subcategorias_lista = []
        todos_lancamentos_categoria = []

        for indice_subcategoria, (subcategoria, dados_subcategoria) in enumerate(subcategorias_ordenadas):
            valor_subcategoria = dados_subcategoria["valor"]
            percentual_subcategoria = (
                valor_subcategoria / valor_categoria * 100
                if valor_categoria > 0
                else 0
            )

            lancamentos = sorted(
                dados_subcategoria["lancamentos"],
                key=lambda item: item["valor"],
                reverse=True,
            )

            todos_lancamentos_categoria.extend(lancamentos)

            subcategorias_lista.append(
                {
                    "id": f"sub_{indice_categoria}_{indice_subcategoria}",
                    "subcategoria": subcategoria,
                    "valor": valor_subcategoria,
                    "valor_fmt": formatar_moeda(valor_subcategoria),
                    "percentual": percentual_subcategoria,
                    "percentual_fmt": f"{percentual_subcategoria:.1f}".replace(".", ",") + "%",
                    "qtd_lancamentos": len(lancamentos),
                    "lancamentos": lancamentos,
                }
            )

        todos_lancamentos_categoria = sorted(
            todos_lancamentos_categoria,
            key=lambda item: item["valor"],
            reverse=True,
        )

        qtd_lancamentos_categoria = sum(
            subcategoria["qtd_lancamentos"]
            for subcategoria in subcategorias_lista
        )

        despesas_por_categoria_lista.append(
            {
                "id": f"cat_{indice_categoria}",
                "modal_id": f"modal_cat_{indice_categoria}",
                "categoria": categoria,
                "valor": valor_categoria,
                "valor_fmt": formatar_moeda(valor_categoria),
                "percentual": percentual_categoria,
                "percentual_fmt": f"{percentual_categoria:.1f}".replace(".", ",") + "%",
                "qtd_lancamentos": qtd_lancamentos_categoria,
                "subcategorias": subcategorias_lista,
                "lancamentos": todos_lancamentos_categoria,
                "cor": estilo["cor"],
                "cor_fundo": estilo["fundo"],
                "cor_borda": estilo["borda"],
            }
        )

    diagnosticos = gerar_diagnostico(
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        total_investimentos=total_investimentos,
        saldo=saldo,
        disponivel_apos_investimentos=disponivel_apos_investimentos,
        comprometimento=comprometimento,
        qtd_a_classificar=qtd_a_classificar,
        maior_categoria=maior_categoria,
        maior_categoria_valor=maior_categoria_valor,
        total_despesas_previsto=total_despesas_previsto,
        total_despesas_realizado=total_despesas_realizado,
        diferenca_despesas=diferenca_despesas,
        percentual_execucao_despesas=percentual_execucao_despesas,
        saldo_percentual_receita=saldo_percentual_receita,
        percentual_investimento_receita=percentual_investimento_receita,
        maior_despesa=maior_despesa,
    )

    registros_para_evolucao = registros_ano if registros_ano is not None else registros
    evolucao_mensal = calcular_evolucao_mensal(registros_para_evolucao)

    orcamento_por_categoria = calcular_orcamento_por_categoria(
        registros_realizados=registros,
        registros_orcamento=registros_orcamento,
    )

    lancamentos_receitas = ordenar_lancamentos_por_valor(lancamentos_receitas)
    lancamentos_despesas = ordenar_lancamentos_por_valor(lancamentos_despesas)
    lancamentos_investimentos = ordenar_lancamentos_por_valor(lancamentos_investimentos)

    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "total_investimentos": total_investimentos,
        "total_transferencias": total_transferencias,
        "saldo": saldo,
        "disponivel_apos_investimentos": disponivel_apos_investimentos,
        "comprometimento": comprometimento,
        "saldo_percentual_receita": saldo_percentual_receita,
        "percentual_investimento_receita": percentual_investimento_receita,
        "disponivel_percentual_receita": disponivel_percentual_receita,
        "media_despesas": media_despesas,
        "qtd_receitas": qtd_receitas,
        "qtd_despesas": qtd_despesas,
        "qtd_investimentos": qtd_investimentos,
        "qtd_transferencias": qtd_transferencias,
        "qtd_a_classificar": qtd_a_classificar,
        "total_lancamentos": len(registros),

        "total_receitas_fmt": formatar_moeda(total_receitas),
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "total_investimentos_fmt": formatar_moeda(total_investimentos),
        "total_transferencias_fmt": formatar_moeda(total_transferencias),
        "saldo_fmt": formatar_moeda(saldo),
        "disponivel_apos_investimentos_fmt": formatar_moeda(disponivel_apos_investimentos),
        "comprometimento_fmt": f"{comprometimento:.1f}".replace(".", ",") + "%",
        "saldo_percentual_receita_fmt": f"{saldo_percentual_receita:.1f}".replace(".", ",") + "%",
        "percentual_investimento_receita_fmt": f"{percentual_investimento_receita:.1f}".replace(".", ",") + "%",
        "disponivel_percentual_receita_fmt": f"{disponivel_percentual_receita:.1f}".replace(".", ",") + "%",
        "media_despesas_fmt": formatar_moeda(media_despesas),

        "total_receitas_previsto": total_receitas_previsto,
        "total_receitas_realizado": total_receitas_realizado,
        "total_despesas_previsto": total_despesas_previsto,
        "total_despesas_realizado": total_despesas_realizado,
        "total_investimentos_previsto": total_investimentos_previsto,
        "total_investimentos_realizado": total_investimentos_realizado,
        "diferenca_receitas": diferenca_receitas,
        "diferenca_despesas": diferenca_despesas,
        "diferenca_investimentos": diferenca_investimentos,
        "percentual_execucao_receitas": percentual_execucao_receitas,
        "percentual_execucao_despesas": percentual_execucao_despesas,
        "percentual_execucao_investimentos": percentual_execucao_investimentos,

        "total_receitas_previsto_fmt": formatar_moeda(total_receitas_previsto),
        "total_receitas_realizado_fmt": formatar_moeda(total_receitas_realizado),
        "total_despesas_previsto_fmt": formatar_moeda(total_despesas_previsto),
        "total_despesas_realizado_fmt": formatar_moeda(total_despesas_realizado),
        "total_investimentos_previsto_fmt": formatar_moeda(total_investimentos_previsto),
        "total_investimentos_realizado_fmt": formatar_moeda(total_investimentos_realizado),
        "diferenca_receitas_fmt": formatar_moeda(abs(diferenca_receitas)),
        "diferenca_despesas_fmt": formatar_moeda(abs(diferenca_despesas)),
        "diferenca_investimentos_fmt": formatar_moeda(abs(diferenca_investimentos)),
        "percentual_execucao_receitas_fmt": (
            f"{percentual_execucao_receitas:.1f}".replace(".", ",") + "%"
            if total_receitas_previsto > 0
            else "Sem previsto"
        ),
        "percentual_execucao_despesas_fmt": (
            f"{percentual_execucao_despesas:.1f}".replace(".", ",") + "%"
            if total_despesas_previsto > 0
            else "Sem previsto"
        ),
        "percentual_execucao_investimentos_fmt": (
            f"{percentual_execucao_investimentos:.1f}".replace(".", ",") + "%"
            if total_investimentos_previsto > 0
            else "Sem previsto"
        ),

        "maior_categoria": maior_categoria,
        "maior_categoria_valor": maior_categoria_valor,
        "maior_categoria_valor_fmt": formatar_moeda(maior_categoria_valor),
        "maior_despesa": maior_despesa,

        "despesas_por_categoria": despesas_por_categoria_lista,
        "receitas_por_categoria": [
            {
                "categoria": categoria,
                "valor": valor,
                "valor_fmt": formatar_moeda(valor),
            }
            for categoria, valor in receitas_ordenadas
        ],
        "investimentos_por_categoria": [
            {
                "categoria": categoria,
                "valor": valor,
                "valor_fmt": formatar_moeda(valor),
            }
            for categoria, valor in investimentos_ordenados
        ],
        "top_despesas": top_despesas,
        "diagnosticos": diagnosticos,
        "evolucao_mensal": evolucao_mensal,
        "orcamento_por_categoria": orcamento_por_categoria,
        "lancamentos_receitas": lancamentos_receitas,
        "lancamentos_despesas": lancamentos_despesas,
        "lancamentos_investimentos": lancamentos_investimentos,
    }


def gerar_diagnostico(
    total_receitas: float,
    total_despesas: float,
    total_investimentos: float,
    saldo: float,
    disponivel_apos_investimentos: float,
    comprometimento: float,
    qtd_a_classificar: int,
    maior_categoria: str,
    maior_categoria_valor: float,
    total_despesas_previsto: float,
    total_despesas_realizado: float,
    diferenca_despesas: float,
    percentual_execucao_despesas: float,
    saldo_percentual_receita: float,
    percentual_investimento_receita: float,
    maior_despesa: dict | None,
) -> list[dict]:
    diagnosticos = []

    if total_receitas <= 0:
        diagnosticos.append(
            {
                "tipo": "alerta",
                "titulo": "Receita não identificada",
                "texto": "Não há receita registrada no período filtrado. Isso pode distorcer o cálculo de saldo e comprometimento.",
            }
        )
    else:
        if comprometimento <= 60:
            diagnosticos.append(
                {
                    "tipo": "positivo",
                    "titulo": "Comprometimento saudável",
                    "texto": f"As despesas representam {comprometimento:.1f}% da receita no período. O orçamento está com boa margem de controle.",
                }
            )
        elif comprometimento <= 80:
            diagnosticos.append(
                {
                    "tipo": "atencao",
                    "titulo": "Comprometimento moderado",
                    "texto": f"As despesas representam {comprometimento:.1f}% da receita. Ainda há saldo operacional, mas vale revisar gastos variáveis.",
                }
            )
        else:
            diagnosticos.append(
                {
                    "tipo": "alerta",
                    "titulo": "Comprometimento elevado",
                    "texto": f"As despesas representam {comprometimento:.1f}% da receita. Recomenda-se revisar as maiores categorias de despesa.",
                }
            )

    if saldo >= 0:
        diagnosticos.append(
            {
                "tipo": "positivo",
                "titulo": "Saldo operacional positivo",
                "texto": f"O saldo operacional do período está positivo em {formatar_moeda(saldo)}. Isso representa {saldo_percentual_receita:.1f}% da receita.",
            }
        )
    else:
        diagnosticos.append(
            {
                "tipo": "alerta",
                "titulo": "Saldo operacional negativo",
                "texto": f"O saldo operacional do período está negativo em {formatar_moeda(abs(saldo))}. É necessário revisar despesas e lançamentos pendentes.",
            }
        )

    if total_investimentos > 0:
        diagnosticos.append(
            {
                "tipo": "positivo",
                "titulo": "Investimentos realizados",
                "texto": f"Foram destinados {formatar_moeda(total_investimentos)} para investimentos ou reserva no período, equivalente a {percentual_investimento_receita:.1f}% da receita.",
            }
        )

        if disponivel_apos_investimentos >= 0:
            diagnosticos.append(
                {
                    "tipo": "info",
                    "titulo": "Disponível após investimentos",
                    "texto": f"Após despesas e investimentos, o disponível estimado ficou em {formatar_moeda(disponivel_apos_investimentos)}.",
                }
            )
        else:
            diagnosticos.append(
                {
                    "tipo": "atencao",
                    "titulo": "Investimentos acima da folga operacional",
                    "texto": f"Após despesas e investimentos, o disponível ficou negativo em {formatar_moeda(abs(disponivel_apos_investimentos))}. Avalie se houve uso de saldo anterior ou necessidade de ajuste no planejamento.",
                }
            )

    if qtd_a_classificar > 0:
        diagnosticos.append(
            {
                "tipo": "atencao",
                "titulo": "Lançamentos pendentes de classificação",
                "texto": f"Existem {qtd_a_classificar} lançamento(s) a classificar. Revise esses itens antes de fechar a análise do mês.",
            }
        )

    if maior_categoria and maior_categoria != "Sem despesas" and maior_categoria_valor > 0:
        percentual_maior_categoria = 0.0

        if total_despesas > 0:
            percentual_maior_categoria = (maior_categoria_valor / total_despesas) * 100

        diagnosticos.append(
            {
                "tipo": "info",
                "titulo": "Maior categoria de despesa",
                "texto": f"A maior categoria de despesa é {maior_categoria}, com {formatar_moeda(maior_categoria_valor)}, representando {percentual_maior_categoria:.1f}% das despesas.",
            }
        )

    if maior_despesa:
        diagnosticos.append(
            {
                "tipo": "info",
                "titulo": "Maior despesa individual",
                "texto": f"A maior despesa individual foi {maior_despesa['descricao']}, no valor de {maior_despesa['valor_fmt']}.",
            }
        )

    if total_despesas_previsto > 0:
        if diferenca_despesas > 0:
            diagnosticos.append(
                {
                    "tipo": "alerta" if percentual_execucao_despesas > 115 else "atencao",
                    "titulo": "Despesas acima do previsto",
                    "texto": f"As despesas realizadas superaram o previsto em {formatar_moeda(diferenca_despesas)}. A execução está em {percentual_execucao_despesas:.1f}%.",
                }
            )
        elif diferenca_despesas < 0:
            diagnosticos.append(
                {
                    "tipo": "positivo",
                    "titulo": "Despesas abaixo do previsto",
                    "texto": f"As despesas realizadas ficaram {formatar_moeda(abs(diferenca_despesas))} abaixo do previsto. A execução está em {percentual_execucao_despesas:.1f}%.",
                }
            )
        else:
            diagnosticos.append(
                {
                    "tipo": "positivo",
                    "titulo": "Despesas dentro do previsto",
                    "texto": "As despesas realizadas estão exatamente iguais ao valor previsto para o período.",
                }
            )

    return diagnosticos


@router.get("/financeiro", response_class=HTMLResponse)
async def financeiro_get(request: Request):
    config = obter_configuracao_sistema()

    planilha_google = str(config.get("planilha_google", "") or "").strip()
    ano_base = str(config.get("ano_base", "") or "").strip()

    configuracao_ok = bool(planilha_google)

    return templates.TemplateResponse(
        request=request,
        name="financeiro.html",
        context={
            "config": config,
            "planilha_google": planilha_google,
            "ano_base": ano_base,
            "configuracao_ok": configuracao_ok,
        },
    )


@router.get("/financeiro/analise", response_class=HTMLResponse)
async def analise_financeira_get(
    request: Request,
    periodo_tipo: str = Query("mes_unico"),
    mes_unico: str = Query("MAI"),
    mes_inicio: str = Query("JAN"),
    mes_fim: str = Query("DEZ"),
    ano: str | None = Query(None),
):
    config = obter_configuracao_sistema()
    ano_final = ano or str(config.get("ano_base", date.today().year))

    filtros = {
        "periodo_tipo": periodo_tipo,
        "mes_unico": mes_unico,
        "mes_inicio": mes_inicio,
        "mes_fim": mes_fim,
        "ano": ano_final,
    }

    try:
        registros = ler_base_lancamentos()
        registros_orcamento_todos = ler_orcamento_mensal()

        registros_filtrados = filtrar_por_periodo(
            registros=registros,
            periodo_tipo=periodo_tipo,
            mes_unico=mes_unico,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            ano=ano_final,
        )

        registros_orcamento_filtrados = filtrar_orcamento_por_periodo(
            registros_orcamento=registros_orcamento_todos,
            periodo_tipo=periodo_tipo,
            mes_unico=mes_unico,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            ano=ano_final,
        )

        registros_ano = filtrar_por_periodo(
            registros=registros,
            periodo_tipo="todos",
            mes_unico=mes_unico,
            mes_inicio="JAN",
            mes_fim="DEZ",
            ano=ano_final,
        )

        analise = preparar_analise(
            registros=registros_filtrados,
            registros_ano=registros_ano,
            registros_orcamento=registros_orcamento_filtrados,
        )

        return templates.TemplateResponse(
            request=request,
            name="analise_financeira.html",
            context={
                "erro": None,
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "analise": analise,
                "planilha_google": config.get("planilha_google", ""),
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="analise_financeira.html",
            context={
                "erro": f"Erro ao carregar análise financeira: {e}",
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "analise": preparar_analise([]),
                "planilha_google": config.get("planilha_google", ""),
            },
        )