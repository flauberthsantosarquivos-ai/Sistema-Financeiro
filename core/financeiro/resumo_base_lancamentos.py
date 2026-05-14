from __future__ import annotations

from typing import Any

from core.financeiro.dashboard_base import ler_base_lancamentos, para_float


MESES_VALIDOS = {
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
}


def remover_acentos(valor: str) -> str:
    texto = str(valor or "").upper()

    trocas = {
        "Á": "A",
        "À": "A",
        "Ã": "A",
        "Â": "A",
        "Ä": "A",
        "É": "E",
        "È": "E",
        "Ê": "E",
        "Ë": "E",
        "Í": "I",
        "Ì": "I",
        "Î": "I",
        "Ï": "I",
        "Ó": "O",
        "Ò": "O",
        "Õ": "O",
        "Ô": "O",
        "Ö": "O",
        "Ú": "U",
        "Ù": "U",
        "Û": "U",
        "Ü": "U",
        "Ç": "C",
    }

    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)

    return texto


def normalizar_texto(valor: Any) -> str:
    return str(valor or "").strip()


def normalizar_chave(valor: Any) -> str:
    return remover_acentos(normalizar_texto(valor))


def normalizar_tipo(valor: Any) -> str:
    tipo = normalizar_chave(valor)

    if tipo == "TRANSFERENCIA":
        return "TRANSFERÊNCIA"

    return tipo


def normalizar_mes(valor: Any) -> str:
    mes = normalizar_chave(valor)

    if mes in MESES_VALIDOS:
        return mes

    return mes


def formatar_moeda(valor: float) -> str:
    numero = float(valor or 0)
    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def obter_valor_base_lancamento(item: dict) -> float:
    """
    Usa o mesmo critério da Base/Painel:
    - prioriza VALOR_REALIZADO;
    - se não houver realizado, usa VALOR_PREVISTO.
    """

    valor_realizado = abs(para_float(item.get("VALOR_REALIZADO")))
    valor_previsto = abs(para_float(item.get("VALOR_PREVISTO")))

    if valor_realizado > 0:
        return valor_realizado

    return valor_previsto


def obter_totais_base_lancamentos(
    ano: str,
    mes: str = "",
    tipo: str = "",
    categoria: str = "",
) -> dict:
    """
    Retorna os totais oficiais da BASE_LANCAMENTOS.

    Esta função deve ser usada por cards/resumos financeiros que precisam
    bater com a Base de Lançamentos e com o Painel Gerencial.

    O detalhamento do orçamento pode continuar usando sua própria análise
    de previsto x executado x não orçado.
    """

    ano_filtro = normalizar_texto(ano)
    mes_filtro = normalizar_mes(mes)
    tipo_filtro = normalizar_tipo(tipo)
    categoria_filtro = normalizar_chave(categoria)

    registros = ler_base_lancamentos()

    total_receitas = 0.0
    total_despesas = 0.0
    total_investimentos = 0.0
    total_transferencias = 0.0

    qtd_receitas = 0
    qtd_despesas = 0
    qtd_investimentos = 0
    qtd_transferencias = 0

    for item in registros:
        ano_item = normalizar_texto(item.get("ANO"))
        mes_item = normalizar_mes(item.get("MES"))
        tipo_item = normalizar_tipo(item.get("TIPO"))
        categoria_item = normalizar_chave(item.get("CATEGORIA"))

        if ano_filtro and ano_item != ano_filtro:
            continue

        if mes_filtro and mes_item != mes_filtro:
            continue

        if tipo_filtro and tipo_item != tipo_filtro:
            continue

        if categoria_filtro and categoria_item != categoria_filtro:
            continue

        valor = obter_valor_base_lancamento(item)

        if valor <= 0:
            continue

        if tipo_item == "RECEITA":
            total_receitas += valor
            qtd_receitas += 1

        elif tipo_item == "DESPESA":
            total_despesas += valor
            qtd_despesas += 1

        elif tipo_item == "INVESTIMENTO":
            total_investimentos += valor
            qtd_investimentos += 1

        elif tipo_item == "TRANSFERÊNCIA":
            total_transferencias += valor
            qtd_transferencias += 1

    saldo = total_receitas - total_despesas - total_investimentos

    total_geral = (
        total_receitas
        + total_despesas
        + total_investimentos
        + total_transferencias
    )

    return {
        "receitas": total_receitas,
        "despesas": total_despesas,
        "investimentos": total_investimentos,
        "transferencias": total_transferencias,
        "saldo": saldo,
        "total_geral": total_geral,

        "qtd_receitas": qtd_receitas,
        "qtd_despesas": qtd_despesas,
        "qtd_investimentos": qtd_investimentos,
        "qtd_transferencias": qtd_transferencias,

        "receitas_fmt": formatar_moeda(total_receitas),
        "despesas_fmt": formatar_moeda(total_despesas),
        "investimentos_fmt": formatar_moeda(total_investimentos),
        "transferencias_fmt": formatar_moeda(total_transferencias),
        "saldo_fmt": formatar_moeda(saldo),
        "total_geral_fmt": formatar_moeda(total_geral),
    }