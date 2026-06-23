from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import gspread

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import formatar_moeda, para_float
from core.financeiro.lancamentos_google import abrir_planilha_e_base


NOME_ABA_MOVIMENTACOES = "MOVIMENTACOES_ALIMENTACAO"
NOME_ABA_CONTAS = "CONTAS_ALIMENTACAO"

CONTAS_ALIMENTACAO = ["FLV", "RESTAURANTE", "SUPERMERCADO"]

CABECALHOS_MOVIMENTACOES = [
    "ID_MOVIMENTACAO",
    "DATA",
    "CONTA",
    "TIPO",
    "DESCRICAO",
    "VALOR",
    "CATEGORIA_INTERNA",
    "ORIGEM",
    "STATUS_IMPORTACAO",
    "DATA_ATUALIZACAO",
]

CABECALHOS_CONTAS = [
    "CONTA",
    "SALDO_ATUAL",
    "DATA_SALDO",
    "ORIGEM_SALDO",
    "DATA_ATUALIZACAO",
]

# Identificação estável para extrato manual e futura integração Open Finance.
CONTAS_BANCARIAS_ALIMENTACAO = {
    "FLV": {
        "banco_codigo": "290",
        "banco_nome": "PAGSEGURO INTERNET S/A",
        "agencia": "0001",
        "conta": "33441616-1",
    },
    "RESTAURANTE": {
        "banco_codigo": "290",
        "banco_nome": "PAGSEGURO INTERNET S/A",
        "agencia": "0001",
        "conta": "52546899-7",
    },
    "SUPERMERCADO": {
        "banco_codigo": "290",
        "banco_nome": "PAGSEGURO INTERNET S/A",
        "agencia": "0001",
        "conta": "75322098-7",
    },
}


def normalizar_texto(valor: Any) -> str:
    return str(valor or "").strip()


def normalizar_upper(valor: Any) -> str:
    return normalizar_texto(valor).upper()


def normalizar_identificador_bancario(valor: Any) -> str:
    return "".join(caractere for caractere in normalizar_upper(valor) if caractere.isalnum())


def identificar_conta_alimentacao_por_dados_bancarios(
    banco: Any,
    agencia: Any,
    conta: Any,
) -> str:
    banco_normalizado = normalizar_identificador_bancario(banco)
    agencia_normalizada = normalizar_identificador_bancario(agencia)
    conta_normalizada = normalizar_identificador_bancario(conta)

    for nome_interno, dados in CONTAS_BANCARIAS_ALIMENTACAO.items():
        codigo = normalizar_identificador_bancario(dados["banco_codigo"])
        nome = normalizar_identificador_bancario(dados["banco_nome"])
        agencia_cadastrada = normalizar_identificador_bancario(dados["agencia"])
        conta_cadastrada = normalizar_identificador_bancario(dados["conta"])

        banco_confere = codigo in banco_normalizado or nome in banco_normalizado

        if (
            banco_confere
            and agencia_normalizada == agencia_cadastrada
            and conta_normalizada == conta_cadastrada
        ):
            return nome_interno

    return ""


def obter_planilha():
    config = obter_configuracao_sistema()
    link_planilha = normalizar_texto(config.get("planilha_google"))

    if not link_planilha:
        raise ValueError("Nenhuma planilha Google vinculada foi encontrada nas configurações.")

    planilha, _aba_base = abrir_planilha_e_base(link_planilha)
    return planilha


def formatar_aba(aba, quantidade_colunas: int) -> None:
    try:
        ultima_coluna = chr(64 + min(quantidade_colunas, 26))
        aba.freeze(rows=1)
        aba.format(
            f"A1:{ultima_coluna}1",
            {
                "backgroundColor": {"red": 0.09, "green": 0.21, "blue": 0.47},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                },
                "horizontalAlignment": "CENTER",
            },
        )
        aba.format(f"A:{ultima_coluna}", {"verticalAlignment": "MIDDLE"})
    except Exception:
        pass


def obter_ou_criar_aba(nome: str, cabecalhos: list[str]):
    planilha = obter_planilha()

    try:
        aba = planilha.worksheet(nome)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(title=nome, rows=1000, cols=len(cabecalhos))
        aba.update("A1", [cabecalhos], value_input_option="USER_ENTERED")
        formatar_aba(aba, len(cabecalhos))
        return aba

    valores = aba.get_all_values()

    if not valores:
        aba.update("A1", [cabecalhos], value_input_option="USER_ENTERED")
        formatar_aba(aba, len(cabecalhos))
        return aba

    cabecalhos_atuais = valores[0][:len(cabecalhos)]

    # Evita gravar dados deslocados caso a aba tenha estrutura antiga ou quebrada.
    if cabecalhos_atuais != cabecalhos:
        raise ValueError(
            f"A aba {nome} possui cabeçalhos diferentes do esperado. "
            "Exclua somente essa aba na planilha e abra novamente o módulo Alimentação."
        )

    return aba


def obter_aba_movimentacoes():
    return obter_ou_criar_aba(NOME_ABA_MOVIMENTACOES, CABECALHOS_MOVIMENTACOES)


def obter_aba_contas():
    aba = obter_ou_criar_aba(NOME_ABA_CONTAS, CABECALHOS_CONTAS)
    garantir_contas_padrao(aba)
    return aba


def garantir_contas_padrao(aba) -> None:
    valores = aba.get_all_values()
    existentes = {
        normalizar_upper(linha[0])
        for linha in valores[1:]
        if linha and normalizar_texto(linha[0])
    }

    novas = []
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    for conta in CONTAS_ALIMENTACAO:
        if conta not in existentes:
            novas.append([conta, 0, "", "MANUAL", agora])

    if novas:
        primeira_linha = len(valores) + 1
        ultima_linha = primeira_linha + len(novas) - 1
        aba.update(
            f"A{primeira_linha}:E{ultima_linha}",
            novas,
            value_input_option="USER_ENTERED",
        )
        formatar_aba(aba, len(CABECALHOS_CONTAS))


def linha_para_dict(cabecalhos: list[str], linha: list[str]) -> dict:
    return {
        cabecalho: linha[indice] if indice < len(linha) else ""
        for indice, cabecalho in enumerate(cabecalhos)
    }


def ler_movimentacoes() -> list[dict]:
    aba = obter_aba_movimentacoes()
    valores = aba.get_all_values()

    if len(valores) <= 1:
        return []

    registros = []

    for linha in valores[1:]:
        if not any(normalizar_texto(celula) for celula in linha):
            continue

        item = linha_para_dict(CABECALHOS_MOVIMENTACOES, linha)
        item["CONTA"] = normalizar_upper(item.get("CONTA"))
        item["TIPO"] = normalizar_upper(item.get("TIPO"))
        item["VALOR_NUM"] = abs(para_float(item.get("VALOR")))
        item["VALOR_FMT"] = formatar_moeda(item["VALOR_NUM"])
        registros.append(item)

    return registros


def ler_contas() -> list[dict]:
    aba = obter_aba_contas()
    valores = aba.get_all_values()

    mapa: dict[str, dict] = {}

    for linha in valores[1:]:
        if not any(normalizar_texto(celula) for celula in linha):
            continue

        item = linha_para_dict(CABECALHOS_CONTAS, linha)
        conta = normalizar_upper(item.get("CONTA"))

        if not conta:
            continue

        saldo = abs(para_float(item.get("SALDO_ATUAL")))

        mapa[conta] = {
            "conta": conta,
            "saldo_atual": saldo,
            "saldo_atual_fmt": formatar_moeda(saldo),
            "data_saldo": normalizar_texto(item.get("DATA_SALDO")),
            "origem_saldo": normalizar_texto(item.get("ORIGEM_SALDO")) or "MANUAL",
            "data_atualizacao": normalizar_texto(item.get("DATA_ATUALIZACAO")),
        }

    return [
        mapa.get(
            conta,
            {
                "conta": conta,
                "saldo_atual": 0.0,
                "saldo_atual_fmt": formatar_moeda(0),
                "data_saldo": "",
                "origem_saldo": "MANUAL",
                "data_atualizacao": "",
            },
        )
        for conta in CONTAS_ALIMENTACAO
    ]


def atualizar_saldos_contas(
    saldos: dict[str, Any],
    data_saldo: str = "",
    origem: str = "EXTRATO_PAGBANK",
) -> None:
    aba = obter_aba_contas()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    linhas = [
        [
            conta,
            abs(para_float(saldos.get(conta, 0))),
            data_saldo,
            origem,
            agora,
        ]
        for conta in CONTAS_ALIMENTACAO
    ]

    # Atualiza sempre A2:E4, preservando cabeçalhos A1:E1.
    aba.update("A2:E4", linhas, value_input_option="USER_ENTERED")
    formatar_aba(aba, len(CABECALHOS_CONTAS))


def _chave_movimentacao_extrato(
    data: str,
    conta: str,
    descricao: str,
    valor: float,
    tipo: str,
) -> str:
    return "|".join(
        [
            normalizar_texto(data),
            normalizar_upper(conta),
            normalizar_upper(descricao),
            f"{abs(float(valor)):.2f}",
            normalizar_upper(tipo),
        ]
    )


def importar_movimentacoes_extrato(
    conta: str,
    movimentacoes: list[dict],
    saldo_atual: Any = "",
    data_saldo: str = "",
) -> dict:
    conta = normalizar_upper(conta)

    if conta not in CONTAS_ALIMENTACAO:
        raise ValueError("Conta de alimentação inválida.")

    existentes = {
        _chave_movimentacao_extrato(
            item.get("DATA", ""),
            item.get("CONTA", ""),
            item.get("DESCRICAO", ""),
            item.get("VALOR_NUM", 0),
            item.get("TIPO", ""),
        )
        for item in ler_movimentacoes()
    }

    novas_linhas = []
    importadas = 0
    duplicadas = 0
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    for mov in movimentacoes:
        data = normalizar_texto(mov.get("data") or mov.get("DATA"))
        descricao = normalizar_texto(mov.get("descricao") or mov.get("DESCRICAO"))
        tipo = normalizar_upper(mov.get("tipo") or mov.get("TIPO"))
        valor_bruto = para_float(
            mov.get("valor") if mov.get("valor") is not None else mov.get("VALOR")
        )

        if tipo not in {"ENTRADA", "SAÍDA", "SAIDA"}:
            tipo = "ENTRADA" if valor_bruto > 0 else "SAÍDA"

        if tipo == "SAIDA":
            tipo = "SAÍDA"

        valor = abs(valor_bruto)

        if not data or not descricao or valor <= 0:
            continue

        chave = _chave_movimentacao_extrato(data, conta, descricao, valor, tipo)

        if chave in existentes:
            duplicadas += 1
            continue

        novas_linhas.append(
            [
                str(uuid4()),
                data,
                conta,
                tipo,
                descricao,
                valor,
                normalizar_texto(mov.get("categoria_interna")) or conta,
                "EXTRATO_ALIMENTACAO",
                "IMPORTADO",
                agora,
            ]
        )
        existentes.add(chave)
        importadas += 1

    if novas_linhas:
        aba = obter_aba_movimentacoes()
        valores_atuais = aba.get_all_values()
        primeira_linha = len(valores_atuais) + 1
        ultima_linha = primeira_linha + len(novas_linhas) - 1

        # Escrita explícita em A:J: elimina a possibilidade de deslocar para E:N.
        aba.update(
            f"A{primeira_linha}:J{ultima_linha}",
            novas_linhas,
            value_input_option="USER_ENTERED",
        )
        formatar_aba(aba, len(CABECALHOS_MOVIMENTACOES))

    if normalizar_texto(saldo_atual):
        saldos = {item["conta"]: item["saldo_atual"] for item in ler_contas()}
        saldos[conta] = abs(para_float(saldo_atual))
        atualizar_saldos_contas(
            saldos,
            data_saldo=data_saldo or datetime.now().strftime("%d/%m/%Y"),
            origem="EXTRATO_PAGBANK",
        )

    return {"importadas": importadas, "duplicadas": duplicadas}


def filtrar_movimentacoes_por_referencia(
    registros: list[dict],
    ano: str,
    mes: str,
) -> list[dict]:
    ano = normalizar_texto(ano)
    mes = normalizar_texto(mes).zfill(2)
    resultado = []

    for item in registros:
        data = normalizar_texto(item.get("DATA"))
        partes = data.split("/")

        if len(partes) != 3:
            continue

        if partes[1].zfill(2) == mes and partes[2] == ano:
            resultado.append(item)

    return resultado


def montar_resumo_alimentacao(ano: str, mes: str) -> dict:
    contas = ler_contas()
    registros = filtrar_movimentacoes_por_referencia(ler_movimentacoes(), ano, mes)

    por_conta = {
        conta: {"entradas": 0.0, "saidas": 0.0, "qtd": 0}
        for conta in CONTAS_ALIMENTACAO
    }

    for item in registros:
        conta = item.get("CONTA")

        if conta not in por_conta:
            continue

        valor = float(item.get("VALOR_NUM", 0) or 0)

        if item.get("TIPO") == "ENTRADA":
            por_conta[conta]["entradas"] += valor
        else:
            por_conta[conta]["saidas"] += valor

        por_conta[conta]["qtd"] += 1

    cards = []
    total_saldo = 0.0
    total_entradas = 0.0
    total_saidas = 0.0

    for conta_item in contas:
        conta = conta_item["conta"]
        dados = por_conta[conta]

        total_saldo += conta_item["saldo_atual"]
        total_entradas += dados["entradas"]
        total_saidas += dados["saidas"]

        cards.append(
            {
                **conta_item,
                "entradas": dados["entradas"],
                "entradas_fmt": formatar_moeda(dados["entradas"]),
                "saidas": dados["saidas"],
                "saidas_fmt": formatar_moeda(dados["saidas"]),
                "qtd_movimentacoes": dados["qtd"],
            }
        )

    registros_ordenados = sorted(
        registros,
        key=lambda item: tuple(reversed(item.get("DATA", "").split("/"))),
        reverse=True,
    )

    return {
        "ano": ano,
        "mes": mes,
        "contas": cards,
        "movimentacoes": registros_ordenados,
        "total_saldo": total_saldo,
        "total_saldo_fmt": formatar_moeda(total_saldo),
        "total_entradas": total_entradas,
        "total_entradas_fmt": formatar_moeda(total_entradas),
        "total_saidas": total_saidas,
        "total_saidas_fmt": formatar_moeda(total_saidas),
        "qtd_movimentacoes": len(registros_ordenados),
    }
