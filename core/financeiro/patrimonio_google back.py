from __future__ import annotations

from datetime import datetime
from typing import Any

import gspread

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import formatar_moeda, para_float
from core.financeiro.lancamentos_google import abrir_planilha_e_base


NOME_ABA_PATRIMONIO = "PATRIMONIO_FINANCEIRO"


ATIVOS_PATRIMONIO = [
    "POUP BB",
    "CC BB",
    "POUP CAIXA",
    "CC CAIXA",
    "NUBANK",
    "PAGBANK",
    "AÇÕES NUINVEST",
    "CRIPTOMOEDAS",
    "PICPAY",
    "COFRE",
    "EM MÃOS",
]


SUBDIVISOES_PADRAO = {
    "POUP BB": [
        "VARIAÇÃO 01",
        "VARIAÇÃO 51",
    ],
    "PAGBANK": [
        "FLV",
        "RESTAURANTE",
        "SUPERMERCADO",
    ],
    "CRIPTOMOEDAS": [
        "MERCADO BITCOIN",
        "GATE I.O",
    ],
}


SUBDIVISAO_GERAL = "GERAL"


CABECALHOS_PATRIMONIO = [
    "ANO",
    "MES",
    "DATA_INICIO",
    "DATA_FIM",
    "ATIVO",
    "SUBDIVISAO",
    "VALOR_INICIO",
    "VALOR_FIM",
    "DIFERENCA",
    "PERCENTUAL_VARIACAO",
    "OBSERVACAO",
    "DATA_ATUALIZACAO",
]


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


ORDEM_MESES = [sigla for sigla, _ in MESES_OPCOES]


CORES_EVOLUCAO = [
    "#1d4ed8",
    "#047857",
    "#7c3aed",
    "#ea580c",
    "#dc2626",
    "#0891b2",
    "#9333ea",
    "#65a30d",
    "#be123c",
    "#0f766e",
    "#4338ca",
    "#b45309",
]


def normalizar_texto(valor: Any) -> str:
    return str(valor or "").strip()


def normalizar_upper(valor: Any) -> str:
    return normalizar_texto(valor).upper()


def ordem_ativo(nome_ativo: Any) -> int:
    nome_ativo = normalizar_upper(nome_ativo)

    if nome_ativo in ATIVOS_PATRIMONIO:
        return ATIVOS_PATRIMONIO.index(nome_ativo)

    return 999


def ordem_subdivisao(nome_ativo: Any, nome_subdivisao: Any) -> int:
    ativo = normalizar_upper(nome_ativo)
    subdivisao = normalizar_upper(nome_subdivisao)

    ordem = SUBDIVISOES_PADRAO.get(ativo, [])

    if subdivisao in ordem:
        return ordem.index(subdivisao)

    if subdivisao == SUBDIVISAO_GERAL:
        return 998

    return 999


def obter_planilha():
    config = obter_configuracao_sistema()
    link_planilha = str(config.get("planilha_google", "") or "").strip()

    if not link_planilha:
        raise ValueError("Nenhuma planilha Google vinculada foi encontrada nas configurações.")

    planilha, _aba_base_ignorada = abrir_planilha_e_base(link_planilha)

    return planilha


def obter_ou_criar_aba_patrimonio():
    planilha = obter_planilha()

    try:
        aba = planilha.worksheet(NOME_ABA_PATRIMONIO)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(
            title=NOME_ABA_PATRIMONIO,
            rows=1000,
            cols=len(CABECALHOS_PATRIMONIO),
        )

    garantir_cabecalhos_patrimonio(aba)
    return aba


def garantir_cabecalhos_patrimonio(aba) -> None:
    valores = aba.get_all_values()

    if not valores:
        aba.update("A1", [CABECALHOS_PATRIMONIO])
        formatar_aba_patrimonio(aba)
        return

    cabecalhos_atuais = valores[0]

    if cabecalhos_atuais != CABECALHOS_PATRIMONIO:
        aba.clear()
        aba.update("A1", [CABECALHOS_PATRIMONIO])
        formatar_aba_patrimonio(aba)


def formatar_aba_patrimonio(aba) -> None:
    try:
        aba.freeze(rows=1)

        aba.format(
            "A1:L1",
            {
                "backgroundColor": {"red": 0.09, "green": 0.21, "blue": 0.47},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                },
                "horizontalAlignment": "CENTER",
            },
        )

        aba.format(
            "A:L",
            {
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            },
        )

        aba.format(
            "G:I",
            {
                "numberFormat": {
                    "type": "CURRENCY",
                    "pattern": "R$ #,##0.00",
                },
            },
        )

        aba.format(
            "J:J",
            {
                "numberFormat": {
                    "type": "NUMBER",
                    "pattern": "0.00%",
                },
            },
        )
    except Exception:
        pass


def linha_para_dict(cabecalhos: list[str], linha: list[str]) -> dict:
    item = {}

    for indice, cabecalho in enumerate(cabecalhos):
        item[cabecalho] = linha[indice] if indice < len(linha) else ""

    return item


def obter_subdivisoes_do_ativo(ativo: str) -> list[str]:
    ativo_normalizado = normalizar_upper(ativo)

    if ativo_normalizado in SUBDIVISOES_PADRAO:
        return SUBDIVISOES_PADRAO[ativo_normalizado]

    return [SUBDIVISAO_GERAL]


def montar_itens_formulario_padrao() -> list[dict]:
    itens = []

    for ativo in ATIVOS_PATRIMONIO:
        subdivisoes = obter_subdivisoes_do_ativo(ativo)

        for subdivisao in subdivisoes:
            itens.append(
                {
                    "ATIVO": ativo,
                    "SUBDIVISAO": subdivisao,
                    "VALOR_INICIO": "",
                    "VALOR_FIM": "",
                    "OBSERVACAO": "",
                }
            )

    return itens


def enriquecer_registro(item: dict) -> dict:
    valor_inicio = para_float(item.get("VALOR_INICIO"))
    valor_fim = para_float(item.get("VALOR_FIM"))
    diferenca = valor_fim - valor_inicio

    percentual_variacao = 0.0
    if valor_inicio > 0:
        percentual_variacao = (diferenca / valor_inicio) * 100

    item["ATIVO"] = normalizar_upper(item.get("ATIVO"))
    item["SUBDIVISAO"] = normalizar_upper(item.get("SUBDIVISAO") or SUBDIVISAO_GERAL)

    item["VALOR_INICIO_NUM"] = valor_inicio
    item["VALOR_FIM_NUM"] = valor_fim
    item["DIFERENCA_NUM"] = diferenca
    item["PERCENTUAL_VARIACAO_NUM"] = percentual_variacao

    item["VALOR_INICIO_FMT"] = formatar_moeda(valor_inicio)
    item["VALOR_FIM_FMT"] = formatar_moeda(valor_fim)
    item["DIFERENCA_FMT"] = formatar_moeda(abs(diferenca))
    item["PERCENTUAL_VARIACAO_FMT"] = f"{percentual_variacao:.1f}".replace(".", ",") + "%"

    return item


def ler_registros_patrimonio() -> list[dict]:
    aba = obter_ou_criar_aba_patrimonio()
    valores = aba.get_all_values()

    if len(valores) <= 1:
        return []

    cabecalhos = valores[0]
    registros = []

    for linha in valores[1:]:
        if not any(str(celula).strip() for celula in linha):
            continue

        item = linha_para_dict(cabecalhos, linha)
        item = enriquecer_registro(item)

        registros.append(item)

    return registros


def localizar_linhas_por_ano_mes(registros: list[dict], ano: str, mes: str) -> list[int]:
    ano = str(ano or "").strip()
    mes = normalizar_upper(mes)

    linhas = []

    for indice, item in enumerate(registros, start=2):
        if str(item.get("ANO", "")).strip() == ano and normalizar_upper(item.get("MES")) == mes:
            linhas.append(indice)

    return linhas


def excluir_linhas_por_ano_mes(aba, ano: str, mes: str) -> int:
    registros = ler_registros_patrimonio()
    linhas = localizar_linhas_por_ano_mes(registros, ano, mes)

    for linha in sorted(linhas, reverse=True):
        aba.delete_rows(linha)

    return len(linhas)


def salvar_patrimonio_mensal(dados: dict) -> dict:
    aba = obter_ou_criar_aba_patrimonio()

    ano = str(dados.get("ANO", "") or "").strip()
    mes = normalizar_upper(dados.get("MES"))
    data_inicio = str(dados.get("DATA_INICIO", "") or "").strip()
    data_fim = str(dados.get("DATA_FIM", "") or "").strip()
    observacao_geral = str(dados.get("OBSERVACAO", "") or "").strip()

    if not ano:
        raise ValueError("Informe o ano do patrimônio financeiro.")

    if mes not in ORDEM_MESES:
        raise ValueError("Informe um mês válido para o patrimônio financeiro.")

    itens = dados.get("ITENS", [])

    if not isinstance(itens, list):
        raise ValueError("Os itens do patrimônio financeiro não foram enviados corretamente.")

    linhas_novas = []
    data_atualizacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    total_inicio = 0.0
    total_fim = 0.0

    for item in itens:
        ativo = normalizar_upper(item.get("ATIVO"))
        subdivisao = normalizar_upper(item.get("SUBDIVISAO") or SUBDIVISAO_GERAL)
        valor_inicio = abs(para_float(item.get("VALOR_INICIO")))
        valor_fim = abs(para_float(item.get("VALOR_FIM")))
        observacao_item = str(item.get("OBSERVACAO", "") or "").strip()

        if not ativo:
            continue

        if valor_inicio == 0 and valor_fim == 0 and not observacao_item:
            continue

        diferenca = valor_fim - valor_inicio

        percentual_variacao = 0.0
        if valor_inicio > 0:
            percentual_variacao = diferenca / valor_inicio

        observacao_final = observacao_item or observacao_geral

        linhas_novas.append(
            [
                ano,
                mes,
                data_inicio,
                data_fim,
                ativo,
                subdivisao,
                valor_inicio,
                valor_fim,
                diferenca,
                percentual_variacao,
                observacao_final,
                data_atualizacao,
            ]
        )

        total_inicio += valor_inicio
        total_fim += valor_fim

    registros_atuais = ler_registros_patrimonio()
    linhas_existentes = localizar_linhas_por_ano_mes(registros_atuais, ano, mes)

    if linhas_existentes:
        excluir_linhas_por_ano_mes(aba, ano, mes)
        acao = "atualizado"
    else:
        acao = "criado"

    if linhas_novas:
        aba.append_rows(linhas_novas, value_input_option="USER_ENTERED")

    formatar_aba_patrimonio(aba)

    diferenca_total = total_fim - total_inicio
    percentual_total = 0.0

    if total_inicio > 0:
        percentual_total = (diferenca_total / total_inicio) * 100

    return {
        "acao": acao,
        "ano": ano,
        "mes": mes,
        "total_inicio": total_inicio,
        "total_inicio_fmt": formatar_moeda(total_inicio),
        "total_fim": total_fim,
        "total_fim_fmt": formatar_moeda(total_fim),
        "diferenca": diferenca_total,
        "diferenca_fmt": formatar_moeda(abs(diferenca_total)),
        "percentual_variacao": percentual_total,
        "percentual_variacao_fmt": f"{percentual_total:.1f}".replace(".", ",") + "%",
    }


def filtrar_registros_por_ano_mes(
    registros: list[dict],
    ano: str,
    mes: str,
) -> list[dict]:
    ano = str(ano or "").strip()
    mes = normalizar_upper(mes)

    return [
        item for item in registros
        if str(item.get("ANO", "")).strip() == ano
        and normalizar_upper(item.get("MES")) == mes
    ]


def obter_patrimonio_por_ano_mes(ano: str, mes: str) -> dict | None:
    registros = ler_registros_patrimonio()
    itens_mes = filtrar_registros_por_ano_mes(registros, ano, mes)

    if not itens_mes:
        return None

    primeiro = itens_mes[0]

    itens_mes_ordenados = sorted(
        itens_mes,
        key=lambda item: (
            ordem_ativo(item.get("ATIVO")),
            ordem_subdivisao(item.get("ATIVO"), item.get("SUBDIVISAO")),
            normalizar_upper(item.get("SUBDIVISAO")),
        ),
    )

    return {
        "ANO": primeiro.get("ANO", ano),
        "MES": primeiro.get("MES", mes),
        "DATA_INICIO": primeiro.get("DATA_INICIO", ""),
        "DATA_FIM": primeiro.get("DATA_FIM", ""),
        "OBSERVACAO": primeiro.get("OBSERVACAO", ""),
        "ITENS": itens_mes_ordenados,
    }


def dados_formulario_padrao(ano: str, mes: str) -> dict:
    existente = obter_patrimonio_por_ano_mes(ano, mes)
    itens_padrao = montar_itens_formulario_padrao()

    if existente:
        itens_existentes = existente.get("ITENS", [])

        mapa_existentes = {
            (
                normalizar_upper(item.get("ATIVO")),
                normalizar_upper(item.get("SUBDIVISAO") or SUBDIVISAO_GERAL),
            ): item
            for item in itens_existentes
        }

        itens_formulario = []

        for item_padrao in itens_padrao:
            chave = (
                normalizar_upper(item_padrao.get("ATIVO")),
                normalizar_upper(item_padrao.get("SUBDIVISAO") or SUBDIVISAO_GERAL),
            )

            existente_item = mapa_existentes.get(chave)

            if existente_item:
                itens_formulario.append(
                    {
                        "ATIVO": existente_item.get("ATIVO", item_padrao["ATIVO"]),
                        "SUBDIVISAO": existente_item.get("SUBDIVISAO", item_padrao["SUBDIVISAO"]),
                        "VALOR_INICIO": existente_item.get("VALOR_INICIO", ""),
                        "VALOR_FIM": existente_item.get("VALOR_FIM", ""),
                        "OBSERVACAO": existente_item.get("OBSERVACAO", ""),
                    }
                )
            else:
                itens_formulario.append(
                    {
                        "ATIVO": item_padrao["ATIVO"],
                        "SUBDIVISAO": item_padrao["SUBDIVISAO"],
                        "VALOR_INICIO": "",
                        "VALOR_FIM": "",
                        "OBSERVACAO": "",
                    }
                )

        chaves_formulario = {
            (
                normalizar_upper(item.get("ATIVO")),
                normalizar_upper(item.get("SUBDIVISAO") or SUBDIVISAO_GERAL),
            )
            for item in itens_formulario
        }

        for item in itens_existentes:
            chave = (
                normalizar_upper(item.get("ATIVO")),
                normalizar_upper(item.get("SUBDIVISAO") or SUBDIVISAO_GERAL),
            )

            if chave not in chaves_formulario:
                itens_formulario.append(
                    {
                        "ATIVO": item.get("ATIVO", ""),
                        "SUBDIVISAO": item.get("SUBDIVISAO", SUBDIVISAO_GERAL),
                        "VALOR_INICIO": item.get("VALOR_INICIO", ""),
                        "VALOR_FIM": item.get("VALOR_FIM", ""),
                        "OBSERVACAO": item.get("OBSERVACAO", ""),
                    }
                )

        itens_formulario = sorted(
            itens_formulario,
            key=lambda item: (
                ordem_ativo(item.get("ATIVO")),
                ordem_subdivisao(item.get("ATIVO"), item.get("SUBDIVISAO")),
                normalizar_upper(item.get("SUBDIVISAO")),
            ),
        )

        return {
            "ANO": existente.get("ANO", ano),
            "MES": existente.get("MES", mes),
            "DATA_INICIO": existente.get("DATA_INICIO", ""),
            "DATA_FIM": existente.get("DATA_FIM", ""),
            "OBSERVACAO": existente.get("OBSERVACAO", ""),
            "ITENS": itens_formulario,
        }

    return {
        "ANO": ano,
        "MES": mes,
        "DATA_INICIO": "",
        "DATA_FIM": "",
        "OBSERVACAO": "",
        "ITENS": itens_padrao,
    }


def agrupar_ativos_do_mes(itens_mes: list[dict]) -> list[dict]:
    agrupado: dict[str, dict] = {}

    for item in itens_mes:
        ativo = normalizar_upper(item.get("ATIVO"))
        subdivisao = normalizar_upper(item.get("SUBDIVISAO") or SUBDIVISAO_GERAL)

        if not ativo:
            continue

        if ativo not in agrupado:
            agrupado[ativo] = {
                "nome": ativo,
                "inicio": 0.0,
                "fim": 0.0,
                "diferenca": 0.0,
                "subdivisoes": [],
            }

        inicio = float(item.get("VALOR_INICIO_NUM", 0) or 0)
        fim = float(item.get("VALOR_FIM_NUM", 0) or 0)
        diferenca = fim - inicio

        agrupado[ativo]["inicio"] += inicio
        agrupado[ativo]["fim"] += fim
        agrupado[ativo]["diferenca"] += diferenca

        agrupado[ativo]["subdivisoes"].append(
            {
                "nome": subdivisao,
                "inicio": inicio,
                "fim": fim,
                "diferenca": diferenca,
                "inicio_fmt": formatar_moeda(inicio),
                "fim_fmt": formatar_moeda(fim),
                "diferenca_fmt": formatar_moeda(abs(diferenca)),
                "sinal": "+" if diferenca >= 0 else "-",
            }
        )

    ativos = []
    total_fim = sum(item["fim"] for item in agrupado.values())

    for ativo in agrupado.values():
        participacao = 0.0
        if total_fim > 0:
            participacao = (ativo["fim"] / total_fim) * 100

        ativo["subdivisoes"] = sorted(
            ativo["subdivisoes"],
            key=lambda item: (
                ordem_subdivisao(ativo["nome"], item.get("nome")),
                normalizar_upper(item.get("nome")),
            ),
        )

        ativo["participacao"] = participacao
        ativo["inicio_fmt"] = formatar_moeda(ativo["inicio"])
        ativo["fim_fmt"] = formatar_moeda(ativo["fim"])
        ativo["diferenca_fmt"] = formatar_moeda(abs(ativo["diferenca"]))
        ativo["participacao_fmt"] = f"{participacao:.1f}".replace(".", ",") + "%"
        ativo["sinal"] = "+" if ativo["diferenca"] >= 0 else "-"

        ativo["tem_subdivisoes"] = (
            len(ativo["subdivisoes"]) > 1
            or ativo["subdivisoes"][0]["nome"] != SUBDIVISAO_GERAL
        )

        ativos.append(ativo)

    return sorted(
        ativos,
        key=lambda item: ordem_ativo(item["nome"]),
    )


def obter_meses_disponiveis(registros: list[dict]) -> list[tuple[str, str]]:
    meses_disponiveis = []

    for item in registros:
        chave = (
            str(item.get("ANO", "")).strip(),
            normalizar_upper(item.get("MES")),
        )

        if chave not in meses_disponiveis:
            meses_disponiveis.append(chave)

    return meses_disponiveis


def montar_evolucao(registros_ordenados: list[dict]) -> list[dict]:
    meses_disponiveis = obter_meses_disponiveis(registros_ordenados)
    evolucao = []

    for indice, ano_mes in enumerate(meses_disponiveis):
        ano_item, mes_item = ano_mes

        itens_mes = filtrar_registros_por_ano_mes(
            registros=registros_ordenados,
            ano=ano_item,
            mes=mes_item,
        )

        total_inicio = sum(float(item.get("VALOR_INICIO_NUM", 0) or 0) for item in itens_mes)
        total_fim = sum(float(item.get("VALOR_FIM_NUM", 0) or 0) for item in itens_mes)
        diferenca = total_fim - total_inicio

        percentual_variacao = 0.0
        if total_inicio > 0:
            percentual_variacao = (diferenca / total_inicio) * 100

        evolucao.append(
            {
                "ano": ano_item,
                "mes": mes_item,
                "total_inicio": total_inicio,
                "total_fim": total_fim,
                "diferenca": diferenca,
                "percentual_variacao": percentual_variacao,
                "total_inicio_fmt": formatar_moeda(total_inicio),
                "total_fim_fmt": formatar_moeda(total_fim),
                "diferenca_fmt": formatar_moeda(abs(diferenca)),
                "percentual_variacao_fmt": f"{percentual_variacao:.1f}".replace(".", ",") + "%",
                "sinal": "+" if diferenca >= 0 else "-",
                "cor_barra": CORES_EVOLUCAO[indice % len(CORES_EVOLUCAO)],
            }
        )

    maior_total = max([item["total_fim"] for item in evolucao], default=0)

    for item in evolucao:
        item["percentual_barra"] = (
            item["total_fim"] / maior_total * 100
            if maior_total > 0
            else 0
        )

    return evolucao


def montar_pizza_ativos(ativos: list[dict]) -> dict:
    fatias = []
    gradientes = []
    inicio = 0.0

    for indice, ativo in enumerate(ativos):
        valor_fim = float(ativo.get("fim", 0) or 0)
        percentual = float(ativo.get("participacao", 0) or 0)

        if valor_fim <= 0 or percentual <= 0:
            continue

        cor = CORES_EVOLUCAO[indice % len(CORES_EVOLUCAO)]
        fim = inicio + percentual

        subdivisoes = []
        total_subdivisoes = sum(
            float(sub.get("fim", 0) or 0)
            for sub in ativo.get("subdivisoes", [])
        )

        for indice_sub, sub in enumerate(ativo.get("subdivisoes", [])):
            nome_sub = str(sub.get("nome", "") or "").strip()
            valor_sub = float(sub.get("fim", 0) or 0)

            if not nome_sub or nome_sub == SUBDIVISAO_GERAL or valor_sub <= 0:
                continue

            percentual_sub = 0.0
            if total_subdivisoes > 0:
                percentual_sub = (valor_sub / total_subdivisoes) * 100

            subdivisoes.append(
                {
                    "nome": nome_sub,
                    "valor": valor_sub,
                    "valor_fmt": formatar_moeda(valor_sub),
                    "percentual": percentual_sub,
                    "percentual_fmt": f"{percentual_sub:.1f}".replace(".", ",") + "%",
                    "cor": CORES_EVOLUCAO[(indice + indice_sub + 1) % len(CORES_EVOLUCAO)],
                }
            )

        fatias.append(
            {
                "nome": ativo.get("nome", ""),
                "valor": valor_fim,
                "valor_fmt": ativo.get("fim_fmt", formatar_moeda(valor_fim)),
                "percentual": percentual,
                "percentual_fmt": ativo.get("participacao_fmt", f"{percentual:.1f}".replace(".", ",") + "%"),
                "cor": cor,
                "tem_detalhamento": bool(subdivisoes),
                "subdivisoes": subdivisoes,
            }
        )

        gradientes.append(f"{cor} {inicio:.2f}% {fim:.2f}%")
        inicio = fim

    estilo_gradiente = ", ".join(gradientes)

    if not estilo_gradiente:
        estilo_gradiente = "#e5e7eb 0% 100%"

    return {
        "fatias": fatias,
        "gradiente": estilo_gradiente,
        "tem_dados": bool(fatias),
    }


def montar_resumo_patrimonio(
    ano: str | None = None,
    ano_resumo: str | None = None,
    mes_resumo: str | None = None,
) -> dict:
    registros = ler_registros_patrimonio()

    ano_filtro_evolucao = str(ano or "").strip()

    if ano_filtro_evolucao:
        registros = [
            item for item in registros
            if str(item.get("ANO", "")).strip() == ano_filtro_evolucao
        ]

    registros_ordenados = sorted(
        registros,
        key=lambda item: (
            str(item.get("ANO", "")).strip(),
            ORDEM_MESES.index(normalizar_upper(item.get("MES")))
            if normalizar_upper(item.get("MES")) in ORDEM_MESES
            else 99,
            ordem_ativo(item.get("ATIVO")),
            ordem_subdivisao(item.get("ATIVO"), item.get("SUBDIVISAO")),
            normalizar_upper(item.get("SUBDIVISAO")),
        ),
    )

    ano_resumo_final = str(ano_resumo or ano or "").strip()
    mes_resumo_final = normalizar_upper(mes_resumo)

    meses_disponiveis = obter_meses_disponiveis(registros_ordenados)

    if not ano_resumo_final or not mes_resumo_final:
        if meses_disponiveis:
            ano_resumo_final, mes_resumo_final = meses_disponiveis[-1]
        else:
            ano_resumo_final, mes_resumo_final = "", ""

    itens_mes_resumo = []

    if ano_resumo_final and mes_resumo_final:
        itens_mes_resumo = filtrar_registros_por_ano_mes(
            registros=registros_ordenados,
            ano=ano_resumo_final,
            mes=mes_resumo_final,
        )

    total_inicio_atual = sum(float(item.get("VALOR_INICIO_NUM", 0) or 0) for item in itens_mes_resumo)
    total_fim_atual = sum(float(item.get("VALOR_FIM_NUM", 0) or 0) for item in itens_mes_resumo)
    diferenca_atual = total_fim_atual - total_inicio_atual

    percentual_variacao_atual = 0.0
    if total_inicio_atual > 0:
        percentual_variacao_atual = (diferenca_atual / total_inicio_atual) * 100

    ativos = agrupar_ativos_do_mes(itens_mes_resumo)
    evolucao = montar_evolucao(registros_ordenados)
    pizza_ativos = montar_pizza_ativos(ativos)

    maior_ativo = None
    if ativos:
        maior_ativo = max(ativos, key=lambda item: float(item.get("fim", 0) or 0))

    ultimo = None

    if ano_resumo_final and mes_resumo_final:
        ultimo = {
            "ANO": ano_resumo_final,
            "MES": mes_resumo_final,
            "DATA_INICIO": itens_mes_resumo[0].get("DATA_INICIO", "") if itens_mes_resumo else "",
            "DATA_FIM": itens_mes_resumo[0].get("DATA_FIM", "") if itens_mes_resumo else "",
        }

    return {
        "registros": itens_mes_resumo,
        "registros_todos": registros_ordenados,
        "ultimo": ultimo,
        "ativos": ativos,
        "evolucao": evolucao,
        "pizza_ativos": pizza_ativos,
        "maior_ativo": maior_ativo,

        "ano_resumo": ano_resumo_final,
        "mes_resumo": mes_resumo_final,
        "tem_dados_mes_resumo": bool(itens_mes_resumo),

        "total_inicio_atual": total_inicio_atual,
        "total_inicio_atual_fmt": formatar_moeda(total_inicio_atual),
        "total_fim_atual": total_fim_atual,
        "total_fim_atual_fmt": formatar_moeda(total_fim_atual),
        "diferenca_atual": diferenca_atual,
        "diferenca_atual_fmt": formatar_moeda(abs(diferenca_atual)),
        "percentual_variacao_atual": percentual_variacao_atual,
        "percentual_variacao_atual_fmt": f"{percentual_variacao_atual:.1f}".replace(".", ",") + "%",

        "total_atual": total_fim_atual,
        "total_atual_fmt": formatar_moeda(total_fim_atual),
        "total_anterior": total_inicio_atual,
        "total_anterior_fmt": formatar_moeda(total_inicio_atual),
        "variacao": diferenca_atual,
        "variacao_fmt": formatar_moeda(abs(diferenca_atual)),
        "percentual_variacao": percentual_variacao_atual,
        "percentual_variacao_fmt": f"{percentual_variacao_atual:.1f}".replace(".", ",") + "%",

        "tem_dados": bool(registros_ordenados),
    }