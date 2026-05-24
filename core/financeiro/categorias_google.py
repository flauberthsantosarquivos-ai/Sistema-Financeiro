from __future__ import annotations

from typing import Any

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.lancamentos_google import abrir_planilha_e_base


ABA_CATEGORIAS = "CATEGORIAS"

CABECALHO_CATEGORIAS = [
    "TIPO",
    "CATEGORIA",
    "SUBCATEGORIA",
    "ATIVO",
]


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().upper()

    mapa = str.maketrans(
        "ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
        "AAAAAEEEEIIIIOOOOOUUUUC",
    )

    texto = texto.translate(mapa)

    while "  " in texto:
        texto = texto.replace("  ", " ")

    return texto


def obter_planilha_financeira():
    config = obter_configuracao_sistema()
    link_planilha = str(config.get("planilha_google", "") or "").strip()

    if not link_planilha:
        raise ValueError(
            "Nenhuma planilha Google vinculada foi encontrada nas configurações."
        )

    planilha, _aba_base = abrir_planilha_e_base(link_planilha)

    return planilha


def obter_ou_criar_aba_categorias():
    planilha = obter_planilha_financeira()

    try:
        aba = planilha.worksheet(ABA_CATEGORIAS)
    except Exception:
        aba = planilha.add_worksheet(
            title=ABA_CATEGORIAS,
            rows=500,
            cols=len(CABECALHO_CATEGORIAS),
        )
        aba.update("A1", [CABECALHO_CATEGORIAS])
        return aba

    valores = aba.get_all_values()

    if not valores:
        aba.update("A1", [CABECALHO_CATEGORIAS])
    else:
        cabecalho_atual = valores[0]

        if cabecalho_atual[: len(CABECALHO_CATEGORIAS)] != CABECALHO_CATEGORIAS:
            aba.update("A1", [CABECALHO_CATEGORIAS])

    return aba


def listar_categorias(incluir_inativas: bool = True) -> list[dict[str, str]]:
    aba = obter_ou_criar_aba_categorias()
    valores = aba.get_all_values()

    if not valores:
        return []

    linhas = valores[1:]
    categorias = []

    for indice, linha in enumerate(linhas, start=2):
        if not any(str(celula).strip() for celula in linha):
            continue

        while len(linha) < len(CABECALHO_CATEGORIAS):
            linha.append("")

        item = {
            "LINHA": str(indice),
            "TIPO": normalizar_texto(linha[0]),
            "CATEGORIA": normalizar_texto(linha[1]),
            "SUBCATEGORIA": normalizar_texto(linha[2]),
            "ATIVO": normalizar_texto(linha[3] or "SIM"),
        }

        if not incluir_inativas and item["ATIVO"] != "SIM":
            continue

        categorias.append(item)

    return sorted(
        categorias,
        key=lambda item: (
            item["TIPO"],
            item["CATEGORIA"],
            item["SUBCATEGORIA"],
        ),
    )


def obter_estrutura_categorias(
    incluir_inativas: bool = False,
) -> dict[str, dict[str, list[str]]]:
    categorias = listar_categorias(incluir_inativas=incluir_inativas)

    estrutura: dict[str, dict[str, list[str]]] = {}

    for item in categorias:
        tipo = item["TIPO"]
        categoria = item["CATEGORIA"]
        subcategoria = item["SUBCATEGORIA"]

        if not tipo or not categoria:
            continue

        if tipo not in estrutura:
            estrutura[tipo] = {}

        if categoria not in estrutura[tipo]:
            estrutura[tipo][categoria] = []

        if subcategoria and subcategoria not in estrutura[tipo][categoria]:
            estrutura[tipo][categoria].append(subcategoria)

    return estrutura


def categoria_existe(
    tipo: str,
    categoria: str,
    subcategoria: str,
    incluir_inativas: bool = True,
) -> bool:
    tipo_norm = normalizar_texto(tipo)
    categoria_norm = normalizar_texto(categoria)
    subcategoria_norm = normalizar_texto(subcategoria)

    for item in listar_categorias(incluir_inativas=incluir_inativas):
        if (
            item["TIPO"] == tipo_norm
            and item["CATEGORIA"] == categoria_norm
            and item["SUBCATEGORIA"] == subcategoria_norm
        ):
            return True

    return False


def salvar_categoria(
    tipo: str,
    categoria: str,
    subcategoria: str,
    ativo: str = "SIM",
) -> dict[str, str]:
    tipo_norm = normalizar_texto(tipo)
    categoria_norm = normalizar_texto(categoria)
    subcategoria_norm = normalizar_texto(subcategoria)
    ativo_norm = normalizar_texto(ativo or "SIM")

    if not tipo_norm:
        raise ValueError("Informe o tipo.")

    if not categoria_norm:
        raise ValueError("Informe a categoria.")

    if not subcategoria_norm:
        raise ValueError("Informe a subcategoria.")

    if ativo_norm not in {"SIM", "NÃO", "NAO"}:
        ativo_norm = "SIM"

    if ativo_norm == "NAO":
        ativo_norm = "NÃO"

    aba = obter_ou_criar_aba_categorias()
    valores = aba.get_all_values()

    for indice, linha in enumerate(valores[1:], start=2):
        while len(linha) < len(CABECALHO_CATEGORIAS):
            linha.append("")

        if (
            normalizar_texto(linha[0]) == tipo_norm
            and normalizar_texto(linha[1]) == categoria_norm
            and normalizar_texto(linha[2]) == subcategoria_norm
        ):
            aba.update(
                f"A{indice}:D{indice}",
                [[tipo_norm, categoria_norm, subcategoria_norm, ativo_norm]],
                value_input_option="USER_ENTERED",
            )

            return {
                "TIPO": tipo_norm,
                "CATEGORIA": categoria_norm,
                "SUBCATEGORIA": subcategoria_norm,
                "ATIVO": ativo_norm,
            }

    aba.append_row(
        [tipo_norm, categoria_norm, subcategoria_norm, ativo_norm],
        value_input_option="USER_ENTERED",
    )

    return {
        "TIPO": tipo_norm,
        "CATEGORIA": categoria_norm,
        "SUBCATEGORIA": subcategoria_norm,
        "ATIVO": ativo_norm,
    }


def alterar_status_categoria(linha: int, ativo: str) -> bool:
    aba = obter_ou_criar_aba_categorias()

    ativo_norm = normalizar_texto(ativo or "SIM")

    if ativo_norm == "NAO":
        ativo_norm = "NÃO"

    if ativo_norm not in {"SIM", "NÃO"}:
        ativo_norm = "SIM"

    aba.update(f"D{linha}", [[ativo_norm]], value_input_option="USER_ENTERED")

    return True


def validar_categoria_subcategoria(
    tipo: str,
    categoria: str,
    subcategoria: str,
) -> tuple[str, str, str]:
    tipo_norm = normalizar_texto(tipo)
    categoria_norm = normalizar_texto(categoria)
    subcategoria_norm = normalizar_texto(subcategoria)

    if not categoria_existe(
        tipo=tipo_norm,
        categoria=categoria_norm,
        subcategoria=subcategoria_norm,
        incluir_inativas=False,
    ):
        raise ValueError(
            "Categoria/subcategoria não cadastrada ou inativa: "
            f"{tipo_norm} / {categoria_norm} / {subcategoria_norm}"
        )

    return tipo_norm, categoria_norm, subcategoria_norm
