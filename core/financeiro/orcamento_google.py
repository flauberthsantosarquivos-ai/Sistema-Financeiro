from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import ler_base_lancamentos
from core.financeiro.lancamentos_google import abrir_planilha_e_base
from core.financeiro.resumo_base_lancamentos import obter_valor_base_lancamento


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

NOMES_MESES = {
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

TIPOS_ORCAMENTO = {
    "RECEITA",
    "DESPESA",
    "INVESTIMENTO",
    "TRANSFERÊNCIA",
    "TRANSFERENCIA",
}


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


def normalizar_chave(valor) -> str:
    return remover_acentos(normalizar_texto(valor))


def normalizar_tipo(valor) -> str:
    tipo = normalizar_chave(valor)

    if tipo == "TRANSFERENCIA":
        return "TRANSFERÊNCIA"

    return tipo


def normalizar_subcategoria_para_orcamento(
    categoria: str,
    subcategoria: str,
    descricao: str = "",
) -> str:
    categoria_n = normalizar_chave(categoria)
    subcategoria_n = normalizar_chave(subcategoria)
    descricao_n = normalizar_chave(descricao)

    if categoria_n == "EDUCACAO":
        if (
            "ESCOLA EVA" in subcategoria_n
            or "ESCOLA EVA" in descricao_n
            or "ISAAC" in subcategoria_n
            or "ISAAC" in descricao_n
        ):
            return "ESCOLA"

    if categoria_n == "SAUDE":
        if (
            "FARMACIA" in subcategoria_n
            or "FARMACIA" in descricao_n
            or "DROGARIA" in subcategoria_n
            or "DROGARIA" in descricao_n
            or "MEDICAMENTO" in subcategoria_n
            or "MEDICAMENTO" in descricao_n
            or "REMEDIO" in subcategoria_n
            or "REMEDIO" in descricao_n
        ):
            return "FARMACIA"

    return subcategoria_n


def para_float_brasil(valor) -> float:
    texto = str(valor or "").strip()

    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "").replace("\u00a0", "")

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


def formatar_percentual(valor: float) -> str:
    numero = float(valor or 0)
    return f"{numero:.1f}%".replace(".", ",")


def nome_mes(sigla: str) -> str:
    sigla_normalizada = normalizar_upper(sigla)
    return NOMES_MESES.get(sigla_normalizada, sigla_normalizada)


def linha_para_registro(linha: list[str]) -> dict:
    linha_completa = linha + [""] * (len(CABECALHOS_ORCAMENTO) - len(linha))

    item = {
        cabecalho: linha_completa[indice]
        for indice, cabecalho in enumerate(CABECALHOS_ORCAMENTO)
    }

    valor_previsto = para_float_brasil(item.get("VALOR_PREVISTO"))

    categoria = normalizar_chave(item.get("CATEGORIA"))
    subcategoria = normalizar_subcategoria_para_orcamento(
        categoria=categoria,
        subcategoria=item.get("SUBCATEGORIA"),
        descricao=item.get("OBSERVACAO"),
    )

    item["TIPO"] = normalizar_tipo(item.get("TIPO"))
    item["CATEGORIA"] = categoria
    item["SUBCATEGORIA"] = subcategoria
    item["MES"] = normalizar_upper(item.get("MES"))
    item["ANO"] = normalizar_texto(item.get("ANO"))

    item["VALOR_PREVISTO_NUM"] = valor_previsto
    item["VALOR_PREVISTO_FMT"] = formatar_moeda(valor_previsto)
    item["VALOR_PREVISTO_RAW"] = formatar_numero_brasil(valor_previsto)

    return item


def ler_orcamento_mensal() -> list[dict]:
    _, aba = abrir_planilha_e_orcamento()
    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        return []

    registros = []

    for linha in valores[1:]:
        registros.append(linha_para_registro(linha))

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
    tipo = normalizar_tipo(tipo)
    categoria = normalizar_chave(categoria)

    filtrados = []

    for item in registros:
        item_ano = normalizar_texto(item.get("ANO"))
        item_mes = normalizar_upper(item.get("MES"))
        item_tipo = normalizar_tipo(item.get("TIPO"))
        item_categoria = normalizar_chave(item.get("CATEGORIA"))

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
        registro = linha_para_registro(linha)

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
    tipo = normalizar_tipo(tipo)
    categoria = normalizar_chave(categoria)
    subcategoria = normalizar_subcategoria_para_orcamento(
        categoria=categoria,
        subcategoria=subcategoria,
        descricao=observacao,
    )
    valor_previsto_num = para_float_brasil(valor_previsto)
    valor_previsto_formatado = formatar_numero_brasil(valor_previsto_num)
    observacao = normalizar_texto(observacao)

    if not ano:
        raise ValueError("Informe o ano do orçamento.")

    if not mes:
        raise ValueError("Informe o mês do orçamento.")

    if mes not in ORDEM_MESES:
        raise ValueError("Informe um mês válido.")

    if not tipo:
        raise ValueError("Informe o tipo do orçamento.")

    if tipo not in TIPOS_ORCAMENTO:
        raise ValueError("Informe um tipo válido: RECEITA, DESPESA, INVESTIMENTO ou TRANSFERÊNCIA.")

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


def montar_chave_execucao(
    ano: str,
    mes: str,
    tipo: str,
    categoria: str,
    subcategoria: str,
) -> tuple[str, str, str, str, str]:
    subcategoria_final = normalizar_subcategoria_para_orcamento(
        categoria=categoria,
        subcategoria=subcategoria,
    )

    return (
        normalizar_texto(ano),
        normalizar_upper(mes),
        normalizar_tipo(tipo),
        normalizar_chave(categoria),
        subcategoria_final,
    )


def montar_chave_categoria_execucao(
    ano: str,
    mes: str,
    tipo: str,
    categoria: str,
) -> tuple[str, str, str, str]:
    return (
        normalizar_texto(ano),
        normalizar_upper(mes),
        normalizar_tipo(tipo),
        normalizar_chave(categoria),
    )


def localizar_valor_por_chaves(linha: dict, chaves: list[str]):
    mapa = {
        normalizar_chave(chave): valor
        for chave, valor in linha.items()
    }

    for chave in chaves:
        chave_normalizada = normalizar_chave(chave)

        if chave_normalizada in mapa:
            return mapa[chave_normalizada]

    return ""


def linha_base_deve_entrar_no_realizado(linha: dict) -> bool:
    tipo = normalizar_tipo(
        localizar_valor_por_chaves(
            linha,
            [
                "TIPO",
                "TIPO_LANCAMENTO",
                "TIPO LANÇAMENTO",
                "NATUREZA",
            ],
        )
    )

    if not tipo:
        return False

    if tipo not in TIPOS_ORCAMENTO:
        return False

    situacao = normalizar_chave(
        localizar_valor_por_chaves(
            linha,
            [
                "SITUACAO",
                "SITUAÇÃO",
            ],
        )
    )

    if situacao in {"CANCELADO", "CANCELADA", "IGNORADO", "IGNORADA"}:
        return False

    return True


def montar_detalhe_lancamento(linha: dict, valor: float) -> dict:
    data = localizar_valor_por_chaves(linha, ["DATA", "DATA_LANCAMENTO", "DATA LANÇAMENTO"])
    descricao = localizar_valor_por_chaves(linha, ["DESCRICAO", "DESCRIÇÃO", "HISTORICO", "HISTÓRICO"])
    tipo = localizar_valor_por_chaves(linha, ["TIPO", "TIPO_LANCAMENTO", "TIPO LANÇAMENTO"])
    categoria = localizar_valor_por_chaves(linha, ["CATEGORIA", "CATEGORIA_AJUSTADA", "CATEGORIA AJUSTADA"])
    subcategoria = localizar_valor_por_chaves(linha, ["SUBCATEGORIA", "SUB_CATEGORIA", "SUB CATEGORIA"])
    situacao = localizar_valor_por_chaves(linha, ["SITUACAO", "SITUAÇÃO"])
    forma_pagamento = localizar_valor_por_chaves(linha, ["FORMA_PAGAMENTO", "FORMA PAGAMENTO"])
    conta = localizar_valor_por_chaves(linha, ["CONTA"])
    origem = localizar_valor_por_chaves(linha, ["ORIGEM"])

    return {
        "DATA": normalizar_texto(data),
        "DESCRICAO": normalizar_texto(descricao),
        "TIPO": normalizar_tipo(tipo),
        "CATEGORIA": normalizar_chave(categoria),
        "SUBCATEGORIA": normalizar_chave(subcategoria),
        "SITUACAO": normalizar_texto(situacao),
        "FORMA_PAGAMENTO": normalizar_texto(forma_pagamento),
        "CONTA": normalizar_texto(conta),
        "ORIGEM": normalizar_texto(origem),
        "VALOR_NUM": float(valor or 0),
        "VALOR_FMT": formatar_moeda(valor),
    }


def ler_realizado_base_lancamentos(
    ano: str,
    mes: str = "",
    tipo: str = "",
    categoria: str = "",
) -> dict:
    registros = ler_base_lancamentos()

    ano_filtro = normalizar_texto(ano)
    mes_filtro = normalizar_upper(mes)
    tipo_filtro = normalizar_tipo(tipo)
    categoria_filtro = normalizar_chave(categoria)

    realizado_por_subcategoria: dict[tuple[str, str, str, str, str], float] = {}
    realizado_por_categoria: dict[tuple[str, str, str, str], float] = {}
    detalhes_por_subcategoria: dict[tuple[str, str, str, str, str], list[dict]] = {}

    for linha in registros:
        if not linha_base_deve_entrar_no_realizado(linha):
            continue

        ano_linha = normalizar_texto(
            localizar_valor_por_chaves(
                linha,
                ["ANO", "ANO_REFERENCIA", "ANO REF"],
            )
        )

        mes_linha = normalizar_upper(
            localizar_valor_por_chaves(
                linha,
                ["MES", "MÊS", "MES_REFERENCIA", "MÊS_REFERENCIA", "REFERENCIA"],
            )
        )

        tipo_linha = normalizar_tipo(
            localizar_valor_por_chaves(
                linha,
                ["TIPO", "TIPO_LANCAMENTO", "TIPO LANÇAMENTO", "NATUREZA"],
            )
        )

        categoria_linha = normalizar_chave(
            localizar_valor_por_chaves(
                linha,
                ["CATEGORIA", "CATEGORIA_AJUSTADA", "CATEGORIA AJUSTADA"],
            )
        )

        subcategoria_original = localizar_valor_por_chaves(
            linha,
            ["SUBCATEGORIA", "SUB_CATEGORIA", "SUB CATEGORIA"],
        )

        descricao_linha = localizar_valor_por_chaves(
            linha,
            ["DESCRICAO", "DESCRIÇÃO", "HISTORICO", "HISTÓRICO"],
        )

        subcategoria_linha = normalizar_subcategoria_para_orcamento(
            categoria=categoria_linha,
            subcategoria=subcategoria_original,
            descricao=descricao_linha,
        )

        if ano_filtro and ano_linha != ano_filtro:
            continue

        if mes_filtro and mes_linha != mes_filtro:
            continue

        if tipo_filtro and tipo_linha != tipo_filtro:
            continue

        if categoria_filtro and categoria_linha != categoria_filtro:
            continue

        valor_realizado = abs(obter_valor_base_lancamento(linha))

        if valor_realizado <= 0:
            continue

        chave_subcategoria = montar_chave_execucao(
            ano=ano_linha,
            mes=mes_linha,
            tipo=tipo_linha,
            categoria=categoria_linha,
            subcategoria=subcategoria_linha,
        )

        chave_categoria = montar_chave_categoria_execucao(
            ano=ano_linha,
            mes=mes_linha,
            tipo=tipo_linha,
            categoria=categoria_linha,
        )

        realizado_por_subcategoria[chave_subcategoria] = (
            realizado_por_subcategoria.get(chave_subcategoria, 0.0)
            + valor_realizado
        )

        realizado_por_categoria[chave_categoria] = (
            realizado_por_categoria.get(chave_categoria, 0.0)
            + valor_realizado
        )

        detalhes_por_subcategoria.setdefault(chave_subcategoria, []).append(
            montar_detalhe_lancamento(linha, valor_realizado)
        )

    for chave in detalhes_por_subcategoria:
        detalhes_por_subcategoria[chave] = sorted(
            detalhes_por_subcategoria[chave],
            key=lambda item: (
                normalizar_texto(item.get("DATA")),
                normalizar_texto(item.get("DESCRICAO")),
            ),
        )

    return {
        "subcategoria": realizado_por_subcategoria,
        "categoria": realizado_por_categoria,
        "detalhes": detalhes_por_subcategoria,
    }


def aplicar_execucao_ao_orcamento(
    registros: list[dict],
    ano: str,
    mes: str = "",
    tipo: str = "",
    categoria: str = "",
) -> list[dict]:
    mapas_realizado = ler_realizado_base_lancamentos(
        ano=ano,
        mes=mes,
        tipo=tipo,
        categoria=categoria,
    )

    realizado_por_subcategoria = mapas_realizado.get("subcategoria", {})
    realizado_por_categoria = mapas_realizado.get("categoria", {})
    detalhes_por_subcategoria = mapas_realizado.get("detalhes", {})

    registros_enriquecidos = []
    chaves_orcadas = set()

    for item in registros:
        previsto = float(item.get("VALOR_PREVISTO_NUM", 0) or 0)

        chave_subcategoria = montar_chave_execucao(
            ano=item.get("ANO", ""),
            mes=item.get("MES", ""),
            tipo=item.get("TIPO", ""),
            categoria=item.get("CATEGORIA", ""),
            subcategoria=item.get("SUBCATEGORIA", ""),
        )

        chave_categoria = montar_chave_categoria_execucao(
            ano=item.get("ANO", ""),
            mes=item.get("MES", ""),
            tipo=item.get("TIPO", ""),
            categoria=item.get("CATEGORIA", ""),
        )

        chaves_orcadas.add(chave_subcategoria)

        realizado_subcategoria = realizado_por_subcategoria.get(chave_subcategoria, 0.0)
        realizado_categoria = realizado_por_categoria.get(chave_categoria, 0.0)
        detalhes = detalhes_por_subcategoria.get(chave_subcategoria, [])

        falta_subcategoria = max(previsto - realizado_subcategoria, 0.0)
        excesso_subcategoria = max(realizado_subcategoria - previsto, 0.0)

        percentual_subcategoria = 0.0
        if previsto > 0:
            percentual_subcategoria = realizado_subcategoria / previsto * 100

        if realizado_subcategoria <= 0:
            status_execucao = "NÃO INICIADO"
            classe_execucao = "red"
        elif realizado_subcategoria < previsto:
            status_execucao = "EM ANDAMENTO"
            classe_execucao = "amber"
        elif realizado_subcategoria == previsto:
            status_execucao = "EXECUTADO"
            classe_execucao = "green"
        else:
            status_execucao = "ESTOURADO"
            classe_execucao = "red"

        item_enriquecido = dict(item)
        item_enriquecido.update(
            {
                "VALOR_REALIZADO_NUM": realizado_subcategoria,
                "VALOR_REALIZADO_FMT": formatar_moeda(realizado_subcategoria),
                "VALOR_FALTANTE_NUM": falta_subcategoria,
                "VALOR_FALTANTE_FMT": formatar_moeda(falta_subcategoria),
                "VALOR_EXCESSO_NUM": excesso_subcategoria,
                "VALOR_EXCESSO_FMT": formatar_moeda(excesso_subcategoria),
                "PERCENTUAL_EXECUTADO": percentual_subcategoria,
                "PERCENTUAL_EXECUTADO_FMT": formatar_percentual(percentual_subcategoria),
                "STATUS_EXECUCAO": status_execucao,
                "CLASSE_EXECUCAO": classe_execucao,
                "VALOR_REALIZADO_CATEGORIA_NUM": realizado_categoria,
                "VALOR_REALIZADO_CATEGORIA_FMT": formatar_moeda(realizado_categoria),
                "ITEM_NAO_ORCADO": False,
                "LANCAMENTOS_DETALHE": detalhes,
                "QTD_LANCAMENTOS_DETALHE": len(detalhes),
            }
        )

        registros_enriquecidos.append(item_enriquecido)

    for chave_subcategoria, valor_realizado in realizado_por_subcategoria.items():
        if chave_subcategoria in chaves_orcadas:
            continue

        if valor_realizado <= 0:
            continue

        ano_linha, mes_linha, tipo_linha, categoria_linha, subcategoria_linha = chave_subcategoria

        chave_categoria = montar_chave_categoria_execucao(
            ano=ano_linha,
            mes=mes_linha,
            tipo=tipo_linha,
            categoria=categoria_linha,
        )

        realizado_categoria = realizado_por_categoria.get(chave_categoria, 0.0)
        detalhes = detalhes_por_subcategoria.get(chave_subcategoria, [])

        item_virtual = {
            "ID": f"NAO_ORCADO::{ano_linha}::{mes_linha}::{tipo_linha}::{categoria_linha}::{subcategoria_linha}",
            "ANO": ano_linha,
            "MES": mes_linha,
            "TIPO": tipo_linha,
            "CATEGORIA": categoria_linha,
            "SUBCATEGORIA": subcategoria_linha,
            "VALOR_PREVISTO": "0,00",
            "VALOR_PREVISTO_NUM": 0.0,
            "VALOR_PREVISTO_FMT": formatar_moeda(0.0),
            "VALOR_PREVISTO_RAW": "0,00",
            "OBSERVACAO": "Item executado na base, mas sem orçamento previsto.",
            "CRIADO_EM": "",
            "VALOR_REALIZADO_NUM": valor_realizado,
            "VALOR_REALIZADO_FMT": formatar_moeda(valor_realizado),
            "VALOR_FALTANTE_NUM": 0.0,
            "VALOR_FALTANTE_FMT": formatar_moeda(0.0),
            "VALOR_EXCESSO_NUM": valor_realizado,
            "VALOR_EXCESSO_FMT": formatar_moeda(valor_realizado),
            "PERCENTUAL_EXECUTADO": 0.0,
            "PERCENTUAL_EXECUTADO_FMT": "0,0%",
            "STATUS_EXECUCAO": "NÃO ORÇADO",
            "CLASSE_EXECUCAO": "red",
            "VALOR_REALIZADO_CATEGORIA_NUM": realizado_categoria,
            "VALOR_REALIZADO_CATEGORIA_FMT": formatar_moeda(realizado_categoria),
            "ITEM_NAO_ORCADO": True,
            "LANCAMENTOS_DETALHE": detalhes,
            "QTD_LANCAMENTOS_DETALHE": len(detalhes),
        }

        registros_enriquecidos.append(item_virtual)

    return registros_enriquecidos


def montar_resumo_orcamento(registros: list[dict]) -> dict:
    total_receitas = 0.0
    total_despesas = 0.0
    total_investimentos = 0.0
    total_transferencias = 0.0

    total_receitas_realizado = 0.0
    total_despesas_realizado = 0.0
    total_investimentos_realizado = 0.0
    total_transferencias_realizado = 0.0

    total_receitas_nao_orcado = 0.0
    total_despesas_nao_orcado = 0.0
    total_investimentos_nao_orcado = 0.0
    total_transferencias_nao_orcado = 0.0

    for item in registros:
        tipo = normalizar_tipo(item.get("TIPO"))
        previsto = float(item.get("VALOR_PREVISTO_NUM", 0) or 0)
        realizado = float(item.get("VALOR_REALIZADO_NUM", 0) or 0)
        item_nao_orcado = bool(item.get("ITEM_NAO_ORCADO", False))

        if tipo == "RECEITA":
            if item_nao_orcado:
                total_receitas_nao_orcado += realizado
            else:
                total_receitas += previsto

            total_receitas_realizado += realizado

        elif tipo == "DESPESA":
            if item_nao_orcado:
                total_despesas_nao_orcado += realizado
            else:
                total_despesas += previsto

            total_despesas_realizado += realizado

        elif tipo == "INVESTIMENTO":
            if item_nao_orcado:
                total_investimentos_nao_orcado += realizado
            else:
                total_investimentos += previsto

            total_investimentos_realizado += realizado

        elif tipo == "TRANSFERÊNCIA":
            if item_nao_orcado:
                total_transferencias_nao_orcado += realizado
            else:
                total_transferencias += previsto

            total_transferencias_realizado += realizado

    saldo_previsto = total_receitas - total_despesas - total_investimentos

    saldo_realizado = (
        total_receitas_realizado
        - total_despesas_realizado
        - total_investimentos_realizado
    )

    total_previsto_geral = (
        total_receitas
        + total_despesas
        + total_investimentos
        + total_transferencias
    )

    total_realizado_geral = (
        total_receitas_realizado
        + total_despesas_realizado
        + total_investimentos_realizado
        + total_transferencias_realizado
    )

    total_nao_orcado_geral = (
        total_receitas_nao_orcado
        + total_despesas_nao_orcado
        + total_investimentos_nao_orcado
        + total_transferencias_nao_orcado
    )

    total_faltante_geral = max(total_previsto_geral - total_realizado_geral, 0.0)

    percentual_geral = 0.0
    if total_previsto_geral > 0:
        percentual_geral = total_realizado_geral / total_previsto_geral * 100

    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "total_investimentos": total_investimentos,
        "total_transferencias": total_transferencias,
        "saldo_previsto": saldo_previsto,

        "total_receitas_realizado": total_receitas_realizado,
        "total_despesas_realizado": total_despesas_realizado,
        "total_investimentos_realizado": total_investimentos_realizado,
        "total_transferencias_realizado": total_transferencias_realizado,
        "saldo_realizado": saldo_realizado,

        "total_receitas_nao_orcado": total_receitas_nao_orcado,
        "total_despesas_nao_orcado": total_despesas_nao_orcado,
        "total_investimentos_nao_orcado": total_investimentos_nao_orcado,
        "total_transferencias_nao_orcado": total_transferencias_nao_orcado,
        "total_nao_orcado_geral": total_nao_orcado_geral,

        "total_previsto_geral": total_previsto_geral,
        "total_realizado_geral": total_realizado_geral,
        "total_faltante_geral": total_faltante_geral,
        "percentual_geral": percentual_geral,

        "total_receitas_fmt": formatar_moeda(total_receitas),
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "total_investimentos_fmt": formatar_moeda(total_investimentos),
        "total_transferencias_fmt": formatar_moeda(total_transferencias),
        "saldo_previsto_fmt": formatar_moeda(saldo_previsto),

        "total_receitas_realizado_fmt": formatar_moeda(total_receitas_realizado),
        "total_despesas_realizado_fmt": formatar_moeda(total_despesas_realizado),
        "total_investimentos_realizado_fmt": formatar_moeda(total_investimentos_realizado),
        "total_transferencias_realizado_fmt": formatar_moeda(total_transferencias_realizado),
        "saldo_realizado_fmt": formatar_moeda(saldo_realizado),

        "total_receitas_nao_orcado_fmt": formatar_moeda(total_receitas_nao_orcado),
        "total_despesas_nao_orcado_fmt": formatar_moeda(total_despesas_nao_orcado),
        "total_investimentos_nao_orcado_fmt": formatar_moeda(total_investimentos_nao_orcado),
        "total_transferencias_nao_orcado_fmt": formatar_moeda(total_transferencias_nao_orcado),
        "total_nao_orcado_geral_fmt": formatar_moeda(total_nao_orcado_geral),

        "total_previsto_geral_fmt": formatar_moeda(total_previsto_geral),
        "total_realizado_geral_fmt": formatar_moeda(total_realizado_geral),
        "total_faltante_geral_fmt": formatar_moeda(total_faltante_geral),
        "percentual_geral_fmt": formatar_percentual(percentual_geral),
    }


def normalizar_meses_destino(meses_destino: list[str]) -> list[str]:
    meses_normalizados = []

    for mes in meses_destino:
        mes_normalizado = normalizar_upper(mes)

        if not mes_normalizado:
            continue

        if mes_normalizado not in ORDEM_MESES:
            raise ValueError(f"Mês inválido informado: {mes}")

        if mes_normalizado not in meses_normalizados:
            meses_normalizados.append(mes_normalizado)

    return meses_normalizados


def existe_orcamento_no_mes(
    registros: list[dict],
    ano: str,
    mes: str,
) -> bool:
    ano = normalizar_texto(ano)
    mes = normalizar_upper(mes)

    for item in registros:
        if (
            normalizar_texto(item.get("ANO")) == ano
            and normalizar_upper(item.get("MES")) == mes
        ):
            return True

    return False


def obter_meses_com_orcamento_existente(
    registros: list[dict],
    ano: str,
    meses_destino: list[str],
) -> list[str]:
    meses_com_orcamento = []

    for mes in meses_destino:
        if existe_orcamento_no_mes(registros, ano, mes):
            meses_com_orcamento.append(mes)

    return meses_com_orcamento


def excluir_orcamento_por_ano_e_meses(
    aba,
    ano: str,
    meses: list[str],
) -> int:
    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        return 0

    linhas_para_excluir = []

    for indice_linha, linha in enumerate(valores[1:], start=2):
        registro = linha_para_registro(linha)

        if (
            normalizar_texto(registro.get("ANO")) == normalizar_texto(ano)
            and normalizar_upper(registro.get("MES")) in meses
        ):
            linhas_para_excluir.append(indice_linha)

    for indice_linha in sorted(linhas_para_excluir, reverse=True):
        aba.delete_rows(indice_linha)

    return len(linhas_para_excluir)


def montar_chave_orcamento(item: dict) -> tuple[str, str, str, str, str]:
    return (
        normalizar_texto(item.get("ANO")),
        normalizar_upper(item.get("MES")),
        normalizar_tipo(item.get("TIPO")),
        normalizar_chave(item.get("CATEGORIA")),
        normalizar_subcategoria_para_orcamento(
            categoria=item.get("CATEGORIA"),
            subcategoria=item.get("SUBCATEGORIA"),
            descricao=item.get("OBSERVACAO", ""),
        ),
    )


def duplicar_orcamento_para_meses_escolhidos(
    ano: str,
    mes_origem: str,
    meses_destino: list[str],
    substituir_existentes: bool = False,
) -> dict:
    _, aba = abrir_planilha_e_orcamento()

    ano = normalizar_texto(ano)
    mes_origem = normalizar_upper(mes_origem)
    meses_destino = normalizar_meses_destino(meses_destino)

    if not ano:
        raise ValueError("Informe o ano do orçamento.")

    if not mes_origem:
        raise ValueError("Informe o mês de origem.")

    if mes_origem not in ORDEM_MESES:
        raise ValueError("Mês de origem inválido.")

    if not meses_destino:
        raise ValueError("Selecione pelo menos um mês de destino.")

    if mes_origem in meses_destino:
        raise ValueError("O mês de origem não pode ser selecionado como destino.")

    registros = ler_orcamento_mensal()

    registros_origem = [
        item
        for item in registros
        if normalizar_texto(item.get("ANO")) == ano
        and normalizar_upper(item.get("MES")) == mes_origem
    ]

    if not registros_origem:
        raise ValueError(
            f"Não há orçamento cadastrado para {nome_mes(mes_origem)}/{ano}."
        )

    meses_com_orcamento_existente = obter_meses_com_orcamento_existente(
        registros=registros,
        ano=ano,
        meses_destino=meses_destino,
    )

    if meses_com_orcamento_existente and not substituir_existentes:
        nomes = ", ".join(nome_mes(mes) for mes in meses_com_orcamento_existente)

        return {
            "status": "bloqueado",
            "mensagem": (
                f"Já existe orçamento previsto para: {nomes}. "
                f"Marque a opção de substituir orçamento existente se quiser sobrescrever esses meses."
            ),
            "mes_origem": mes_origem,
            "meses_destino": meses_destino,
            "meses_com_orcamento_existente": meses_com_orcamento_existente,
            "itens_origem": len(registros_origem),
            "criados": 0,
            "pulados": 0,
            "excluidos": 0,
            "substituir_existentes": substituir_existentes,
        }

    excluidos = 0

    if substituir_existentes and meses_com_orcamento_existente:
        excluidos = excluir_orcamento_por_ano_e_meses(
            aba=aba,
            ano=ano,
            meses=meses_com_orcamento_existente,
        )

        registros = ler_orcamento_mensal()

    chaves_existentes = {
        montar_chave_orcamento(item)
        for item in registros
    }

    linhas_novas = []
    pulados = 0

    for mes_destino in meses_destino:
        for item in registros_origem:
            tipo = normalizar_tipo(item.get("TIPO"))
            categoria = normalizar_chave(item.get("CATEGORIA"))
            subcategoria = normalizar_subcategoria_para_orcamento(
                categoria=categoria,
                subcategoria=item.get("SUBCATEGORIA"),
                descricao=item.get("OBSERVACAO", ""),
            )

            chave = (
                ano,
                mes_destino,
                tipo,
                categoria,
                subcategoria,
            )

            if chave in chaves_existentes:
                pulados += 1
                continue

            valor_previsto = item.get("VALOR_PREVISTO_RAW") or item.get("VALOR_PREVISTO")
            valor_previsto_num = para_float_brasil(valor_previsto)
            valor_previsto_formatado = formatar_numero_brasil(valor_previsto_num)

            observacao_original = normalizar_texto(item.get("OBSERVACAO"))

            if observacao_original:
                observacao = observacao_original
            else:
                observacao = f"Duplicado de {nome_mes(mes_origem)}/{ano}"

            linhas_novas.append(
                [
                    str(uuid4()),
                    ano,
                    mes_destino,
                    tipo,
                    categoria,
                    subcategoria,
                    valor_previsto_formatado,
                    observacao,
                    datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                ]
            )

            chaves_existentes.add(chave)

    if linhas_novas:
        aba.append_rows(
            linhas_novas,
            value_input_option="USER_ENTERED",
        )

    return {
        "status": "ok",
        "mensagem": "Orçamento duplicado com sucesso.",
        "mes_origem": mes_origem,
        "meses_destino": meses_destino,
        "meses_com_orcamento_existente": meses_com_orcamento_existente,
        "itens_origem": len(registros_origem),
        "criados": len(linhas_novas),
        "pulados": pulados,
        "excluidos": excluidos,
        "substituir_existentes": substituir_existentes,
    }