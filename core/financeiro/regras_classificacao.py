from __future__ import annotations

import re
from typing import Any

from core.financeiro.dashboard_base import para_float
from core.financeiro.lancamentos_google import abrir_planilha_e_base


NOME_ABA_REGRAS = "REGRAS_CLASSIFICACAO"

CABECALHOS_REGRAS = [
    "ATIVO",
    "PRIORIDADE",
    "TERMO_DESCRICAO",
    "VALOR_EXATO",
    "VALOR_MINIMO",
    "VALOR_MAXIMO",
    "TIPO",
    "CATEGORIA",
    "SUBCATEGORIA",
    "CONTA",
    "OBSERVACAO",
]


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().upper()

    substituicoes = {
        "Á": "A",
        "À": "A",
        "Â": "A",
        "Ã": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for origem, destino in substituicoes.items():
        texto = texto.replace(origem, destino)

    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def normalizar_sem_espacos(valor: Any) -> str:
    return re.sub(r"\s+", "", normalizar_texto(valor))


def garantir_aba_regras_classificacao(link_planilha: str):
    """
    Garante que a planilha do cliente tenha a aba REGRAS_CLASSIFICACAO.
    Se a aba não existir, cria com cabeçalhos e exemplos comentados.
    """
    planilha, _ = abrir_planilha_e_base(link_planilha)

    try:
        aba = planilha.worksheet(NOME_ABA_REGRAS)
    except Exception:
        aba = planilha.add_worksheet(
            title=NOME_ABA_REGRAS,
            rows=200,
            cols=len(CABECALHOS_REGRAS),
        )

        aba.update(
            "A1:K1",
            [CABECALHOS_REGRAS],
            value_input_option="USER_ENTERED",
        )

        exemplos = [
            [
                "SIM",
                "1",
                "CAIXA",
                "2500,00",
                "",
                "",
                "DESPESA",
                "ALIMENTAÇÃO",
                "SUPERMERCADO",
                "BANCO PRINCIPAL",
                "Exemplo: transferência mensal para supermercado",
            ],
            [
                "SIM",
                "2",
                "CAIXA",
                "2000,00",
                "",
                "",
                "DESPESA",
                "ALIMENTAÇÃO",
                "RESTAURANTE",
                "BANCO PRINCIPAL",
                "Exemplo: transferência mensal para restaurante",
            ],
            [
                "SIM",
                "3",
                "CAIXA",
                "500,00",
                "",
                "",
                "DESPESA",
                "ALIMENTAÇÃO",
                "FLV",
                "BANCO PRINCIPAL",
                "Exemplo: transferência mensal para FLV",
            ],
            [
                "SIM",
                "4",
                "CAIXA",
                "",
                "2100,00",
                "2250,00",
                "DESPESA",
                "MORADIA",
                "PRESTAÇÃO APARTAMENTO",
                "BANCO PRINCIPAL",
                "Exemplo: prestação do apartamento com faixa de valor",
            ],
        ]

        aba.update(
            f"A2:K{len(exemplos) + 1}",
            exemplos,
            value_input_option="USER_ENTERED",
        )

        try:
            aba.freeze(rows=1)
            aba.format(
                "A1:K1",
                {
                    "textFormat": {"bold": True},
                    "horizontalAlignment": "CENTER",
                    "backgroundColor": {"red": 0.85, "green": 0.90, "blue": 1.00},
                },
            )
        except Exception:
            pass

    return aba


def ler_regras_classificacao(link_planilha: str) -> list[dict[str, Any]]:
    if not link_planilha:
        return []

    aba = garantir_aba_regras_classificacao(link_planilha)

    try:
        registros = aba.get_all_records(expected_headers=CABECALHOS_REGRAS)
    except TypeError:
        registros = aba.get_all_records()
    except Exception:
        return []

    regras = []

    for registro in registros:
        ativo = normalizar_texto(registro.get("ATIVO"))

        if ativo not in {"SIM", "S", "TRUE", "1", "ATIVO"}:
            continue

        termo = str(registro.get("TERMO_DESCRICAO", "")).strip()
        valor_exato = str(registro.get("VALOR_EXATO", "")).strip()
        valor_minimo = str(registro.get("VALOR_MINIMO", "")).strip()
        valor_maximo = str(registro.get("VALOR_MAXIMO", "")).strip()
        tipo = str(registro.get("TIPO", "")).strip()
        categoria = str(registro.get("CATEGORIA", "")).strip()
        subcategoria = str(registro.get("SUBCATEGORIA", "")).strip()

        if not tipo or not categoria:
            continue

        regras.append(
            {
                "ativo": ativo,
                "prioridade": converter_prioridade(registro.get("PRIORIDADE")),
                "termo_descricao": termo,
                "valor_exato": valor_exato,
                "valor_minimo": valor_minimo,
                "valor_maximo": valor_maximo,
                "tipo": tipo,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "conta": str(registro.get("CONTA", "")).strip(),
                "observacao": str(registro.get("OBSERVACAO", "")).strip(),
            }
        )

    regras.sort(key=lambda item: item["prioridade"])

    return regras


def converter_prioridade(valor: Any) -> int:
    try:
        return int(float(str(valor).replace(",", ".").strip()))
    except Exception:
        return 9999


def regra_bate_com_movimentacao(
    regra: dict[str, Any],
    descricao: str,
    valor: float,
) -> bool:
    descricao_normalizada = normalizar_texto(descricao)
    descricao_sem_espacos = normalizar_sem_espacos(descricao)

    termo = str(regra.get("termo_descricao", "")).strip()

    if termo:
        termo_normalizado = normalizar_texto(termo)
        termo_sem_espacos = normalizar_sem_espacos(termo)

        if termo_normalizado not in descricao_normalizada and termo_sem_espacos not in descricao_sem_espacos:
            return False

    valor_abs = round(abs(float(valor or 0)), 2)

    valor_exato = str(regra.get("valor_exato", "")).strip()
    valor_minimo = str(regra.get("valor_minimo", "")).strip()
    valor_maximo = str(regra.get("valor_maximo", "")).strip()

    if valor_exato:
        valor_exato_float = round(abs(para_float(valor_exato)), 2)

        if valor_abs != valor_exato_float:
            return False

    if valor_minimo:
        valor_minimo_float = round(abs(para_float(valor_minimo)), 2)

        if valor_abs < valor_minimo_float:
            return False

    if valor_maximo:
        valor_maximo_float = round(abs(para_float(valor_maximo)), 2)

        if valor_abs > valor_maximo_float:
            return False

    return True


def aplicar_regras_cliente_em_movimentacao(
    movimentacao: dict[str, Any],
    regras: list[dict[str, Any]],
) -> dict[str, Any]:
    descricao = str(movimentacao.get("descricao", "")).strip()
    valor = float(movimentacao.get("valor", 0) or 0)

    for regra in regras:
        if not regra_bate_com_movimentacao(
            regra=regra,
            descricao=descricao,
            valor=valor,
        ):
            continue

        movimentacao["tipo"] = regra.get("tipo") or movimentacao.get("tipo", "")
        movimentacao["categoria"] = regra.get("categoria") or movimentacao.get("categoria", "")
        movimentacao["subcategoria"] = regra.get("subcategoria") or movimentacao.get("subcategoria", "")

        if regra.get("conta"):
            movimentacao["conta"] = regra["conta"]

        if movimentacao["tipo"].upper() == "RECEITA":
            movimentacao["situacao"] = "RECEBIDO"
        else:
            movimentacao["situacao"] = "PAGO"

        observacao_atual = str(movimentacao.get("observacao", "")).strip()
        observacao_regra = regra.get("observacao", "")

        complemento = "Classificado por regra do cliente"

        if observacao_regra:
            complemento += f": {observacao_regra}"

        if observacao_atual:
            movimentacao["observacao"] = f"{observacao_atual}. {complemento}"
        else:
            movimentacao["observacao"] = complemento

        movimentacao["regra_classificacao_aplicada"] = "SIM"

        return movimentacao

    movimentacao["regra_classificacao_aplicada"] = "NAO"

    return movimentacao


def aplicar_regras_cliente_no_resultado(
    resultado: dict[str, Any],
    link_planilha: str,
) -> dict[str, Any]:
    """
    Aplica as regras da aba REGRAS_CLASSIFICACAO sobre as movimentações lidas do extrato.
    Isso é feito antes da prévia ser exibida ao usuário.
    """
    if not resultado:
        return resultado

    movimentacoes = resultado.get("movimentacoes", [])

    if not movimentacoes:
        return resultado

    regras = ler_regras_classificacao(link_planilha)

    if not regras:
        return resultado

    novas_movimentacoes = []

    for movimentacao in movimentacoes:
        novas_movimentacoes.append(
            aplicar_regras_cliente_em_movimentacao(
                movimentacao=movimentacao,
                regras=regras,
            )
        )

    resultado["movimentacoes"] = novas_movimentacoes
    resultado["qtd_regras_cliente"] = len(regras)

    return resultado