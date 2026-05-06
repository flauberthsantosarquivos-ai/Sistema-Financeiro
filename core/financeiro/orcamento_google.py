from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.lancamentos_google import abrir_planilha_e_base


NOME_ABA_ORCAMENTO = "ORCAMENTO_MENSAL"

CABECALHOS_ORCAMENTO = [
    "ID",
    "ANO",
    "MES",
    "TIPO",
    "CATEGORIA",
    "SUBCATEGORIA",
    "VALOR_PREVISTO",
    "OBSERVACAO",
    "CRIADO_EM",
]


def obter_link_planilha_configurada() -> str:
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    if not link_planilha:
        raise ValueError("Nenhuma planilha Google vinculada foi encontrada nas configurações.")

    return link_planilha


def abrir_planilha_e_orcamento():
    link_planilha = obter_link_planilha_configurada()

    planilha, _ = abrir_planilha_e_base(link_planilha)

    try:
        aba = planilha.worksheet(NOME_ABA_ORCAMENTO)
    except Exception:
        aba = planilha.add_worksheet(
            title=NOME_ABA_ORCAMENTO,
            rows=1000,
            cols=len(CABECALHOS_ORCAMENTO),
        )
        aba.update("A1:I1", [CABECALHOS_ORCAMENTO])

    valores = aba.get_all_values()

    if not valores:
        aba.update("A1:I1", [CABECALHOS_ORCAMENTO])
    else:
        primeira_linha = valores[0]

        if primeira_linha != CABECALHOS_ORCAMENTO:
            aba.update("A1:I1", [CABECALHOS_ORCAMENTO])

    return planilha, aba


def normalizar_texto(valor) -> str:
    return str(valor or "").strip()


def normalizar_upper(valor) -> str:
    return normalizar_texto(valor).upper()


def para_float_brasil(valor) -> float:
    texto = str(valor or "").strip()

    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def formatar_moeda(valor: float) -> str:
    numero = float(valor or 0)
    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero_brasil(valor: float) -> str:
    numero = float(valor or 0)
    return f"{numero:.2f}".replace(".", ",")


def ler_orcamento_mensal() -> list[dict]:
    _, aba = abrir_planilha_e_orcamento()

    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        return []

    registros = []

    for linha in valores[1:]:
        linha_completa = linha + [""] * (len(CABECALHOS_ORCAMENTO) - len(linha))

        item = {
            cabecalho: linha_completa[indice]
            for indice, cabecalho in enumerate(CABECALHOS_ORCAMENTO)
        }

        valor_previsto = para_float_brasil(item.get("VALOR_PREVISTO"))

        item["VALOR_PREVISTO_NUM"] = valor_previsto
        item["VALOR_PREVISTO_FMT"] = formatar_moeda(valor_previsto)
        item["VALOR_PREVISTO_RAW"] = formatar_numero_brasil(valor_previsto)

        registros.append(item)

    return registros


def filtrar_orcamento(
    registros: list[dict],
    ano: str,
    mes: str = "",
    tipo: str = "",
    categoria: str = "",
) -> list[dict]:
    ano = normalizar_texto(ano)
    mes = normalizar_upper(mes)
    tipo = normalizar_upper(tipo)
    categoria = normalizar_upper(categoria)

    filtrados = []

    for item in registros:
        item_ano = normalizar_texto(item.get("ANO"))
        item_mes = normalizar_upper(item.get("MES"))
        item_tipo = normalizar_upper(item.get("TIPO"))
        item_categoria = normalizar_upper(item.get("CATEGORIA"))

        if ano and item_ano != ano:
            continue

        if mes and item_mes != mes:
            continue

        if tipo and item_tipo != tipo:
            continue

        if categoria and item_categoria != categoria:
            continue

        filtrados.append(item)

    return filtrados


def localizar_orcamento_por_id(orcamento_id: str):
    _, aba = abrir_planilha_e_orcamento()

    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        raise ValueError("A aba ORCAMENTO_MENSAL está vazia.")

    for indice_linha, linha in enumerate(valores[1:], start=2):
        linha_completa = linha + [""] * (len(CABECALHOS_ORCAMENTO) - len(linha))

        registro = {
            cabecalho: linha_completa[indice]
            for indice, cabecalho in enumerate(CABECALHOS_ORCAMENTO)
        }

        if str(registro.get("ID", "")).strip() == str(orcamento_id).strip():
            return aba, indice_linha, registro

    raise ValueError("Item de orçamento não encontrado.")


def salvar_orcamento(
    ano: str,
    mes: str,
    tipo: str,
    categoria: str,
    subcategoria: str,
    valor_previsto: str,
    observacao: str = "",
    orcamento_id: str | None = None,
) -> str:
    _, aba = abrir_planilha_e_orcamento()

    ano = normalizar_texto(ano)
    mes = normalizar_upper(mes)
    tipo = normalizar_upper(tipo)
    categoria = normalizar_upper(categoria)
    subcategoria = normalizar_upper(subcategoria)
    valor_previsto_num = para_float_brasil(valor_previsto)
    valor_previsto_formatado = formatar_numero_brasil(valor_previsto_num)
    observacao = normalizar_texto(observacao)

    if not ano:
        raise ValueError("Informe o ano do orçamento.")

    if not mes:
        raise ValueError("Informe o mês do orçamento.")

    if not tipo:
        raise ValueError("Informe o tipo do orçamento.")

    if not categoria:
        raise ValueError("Informe a categoria do orçamento.")

    if valor_previsto_num <= 0:
        raise ValueError("Informe um valor previsto maior que zero.")

    if orcamento_id:
        aba_atual, indice_linha, registro_antigo = localizar_orcamento_por_id(orcamento_id)

        criado_em = registro_antigo.get("CRIADO_EM", "")

        linha = [
            orcamento_id,
            ano,
            mes,
            tipo,
            categoria,
            subcategoria,
            valor_previsto_formatado,
            observacao,
            criado_em,
        ]

        aba_atual.update(
            f"A{indice_linha}:I{indice_linha}",
            [linha],
            value_input_option="USER_ENTERED",
        )

        return orcamento_id

    novo_id = str(uuid4())
    criado_em = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    linha = [
        novo_id,
        ano,
        mes,
        tipo,
        categoria,
        subcategoria,
        valor_previsto_formatado,
        observacao,
        criado_em,
    ]

    aba.append_row(linha, value_input_option="USER_ENTERED")

    return novo_id


def excluir_orcamento(orcamento_id: str) -> None:
    aba, indice_linha, _ = localizar_orcamento_por_id(orcamento_id)
    aba.delete_rows(indice_linha)


def montar_resumo_orcamento(registros: list[dict]) -> dict:
    total_receitas = 0.0
    total_despesas = 0.0
    total_transferencias = 0.0

    for item in registros:
        tipo = normalizar_upper(item.get("TIPO"))
        valor = float(item.get("VALOR_PREVISTO_NUM", 0) or 0)

        if tipo == "RECEITA":
            total_receitas += valor
        elif tipo == "DESPESA":
            total_despesas += valor
        elif tipo in {"TRANSFERÊNCIA", "TRANSFERENCIA"}:
            total_transferencias += valor

    saldo_previsto = total_receitas - total_despesas

    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "total_transferencias": total_transferencias,
        "saldo_previsto": saldo_previsto,
        "total_receitas_fmt": formatar_moeda(total_receitas),
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "total_transferencias_fmt": formatar_moeda(total_transferencias),
        "saldo_previsto_fmt": formatar_moeda(saldo_previsto),
    }