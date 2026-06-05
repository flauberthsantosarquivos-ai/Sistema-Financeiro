from __future__ import annotations

from typing import Any, Dict, List, Tuple

import gspread

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.lancamentos_google import abrir_planilha_e_base


ABA_CATEGORIAS = "CATEGORIAS"

CABECALHOS_CATEGORIAS = [
    "TIPO",
    "CATEGORIA",
    "SUBCATEGORIA",
    "ATIVO",
]

TIPOS_OFICIAIS = [
    "RECEITA",
    "DESPESA",
    "INVESTIMENTO",
    "TRANSFERÊNCIA",
]

CATEGORIAS_PADRAO = [
    # DESPESAS
    ("DESPESA", "CASA", "PRESTAÇÃO AP", "SIM"),
    ("DESPESA", "CASA", "CONDOMÍNIO", "SIM"),
    ("DESPESA", "CASA", "AMORTIZAÇÃO", "SIM"),
    ("DESPESA", "CASA", "ENERGIA ELÉTRICA", "SIM"),
    ("DESPESA", "CASA", "ÁGUA", "SIM"),
    ("DESPESA", "CASA", "GÁS", "SIM"),
    ("DESPESA", "CASA", "INTERNET", "SIM"),
    ("DESPESA", "CASA", "IPTU", "SIM"),
    ("DESPESA", "ALIMENTAÇÃO", "SUPERMERCADO", "SIM"),
    ("DESPESA", "ALIMENTAÇÃO", "FLV", "SIM"),
    ("DESPESA", "ALIMENTAÇÃO", "RESTAURANTE", "SIM"),
    ("DESPESA", "ALIMENTAÇÃO", "PADARIA", "SIM"),
    ("DESPESA", "TRANSPORTE", "COMBUSTÍVEL", "SIM"),
    ("DESPESA", "TRANSPORTE", "UBER", "SIM"),
    ("DESPESA", "TRANSPORTE", "MANUTENÇÃO", "SIM"),
    ("DESPESA", "SAÚDE", "PLANO DE SAÚDE", "SIM"),
    ("DESPESA", "SAÚDE", "FARMÁCIA", "SIM"),
    ("DESPESA", "SAÚDE", "CONSULTAS", "SIM"),
    ("DESPESA", "EDUCAÇÃO", "ESCOLA", "SIM"),
    ("DESPESA", "EDUCAÇÃO", "CURSO", "SIM"),
    ("DESPESA", "EDUCAÇÃO", "MATERIAL", "SIM"),
    ("DESPESA", "CARTÃO", "FATURA CARTÃO", "SIM"),
    ("DESPESA", "SERVIÇOS", "TELEFONE", "SIM"),
    ("DESPESA", "SERVIÇOS", "STREAMING", "SIM"),
    ("DESPESA", "SERVIÇOS", "ASSINATURAS", "SIM"),
    ("DESPESA", "OUTROS", "OUTROS", "SIM"),
    # RECEITAS
    ("RECEITA", "SALÁRIO", "SALÁRIO PRINCIPAL", "SIM"),
    ("RECEITA", "SALÁRIO", "ADIANTAMENTO", "SIM"),
    ("RECEITA", "RENDIMENTOS", "JUROS", "SIM"),
    ("RECEITA", "RENDIMENTOS", "DIVIDENDOS", "SIM"),
    ("RECEITA", "OUTRAS RECEITAS", "OUTRAS RECEITAS", "SIM"),
    # INVESTIMENTOS
    ("INVESTIMENTO", "RESERVA", "TESOURO", "SIM"),
    ("INVESTIMENTO", "RESERVA", "CDB", "SIM"),
    ("INVESTIMENTO", "RESERVA", "POUPANÇA", "SIM"),
    ("INVESTIMENTO", "RESERVA", "FUNDO", "SIM"),
    ("INVESTIMENTO", "RENDA VARIÁVEL", "AÇÕES", "SIM"),
    ("INVESTIMENTO", "RENDA VARIÁVEL", "CRIPTO", "SIM"),
    ("INVESTIMENTO", "OUTROS", "OUTROS", "SIM"),
    # TRANSFERÊNCIAS
    ("TRANSFERÊNCIA", "CONTAS PRÓPRIAS", "TRANSFERÊNCIA ENTRE CONTAS", "SIM"),
    ("TRANSFERÊNCIA", "CONTAS PRÓPRIAS", "APORTE", "SIM"),
    ("TRANSFERÊNCIA", "CONTAS PRÓPRIAS", "RESGATE", "SIM"),
]


_MAPA_ACENTOS = str.maketrans(
    "ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
    "AAAAAEEEEIIIIOOOOOUUUUC",
)


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().upper()
    texto = " ".join(texto.split())
    return texto


def normalizar_sem_acentos(valor: Any) -> str:
    return normalizar_texto(valor).translate(_MAPA_ACENTOS)


def normalizar_tipo(valor: Any) -> str:
    texto = normalizar_sem_acentos(valor)

    if texto == "TRANSFERENCIA":
        return "TRANSFERÊNCIA"

    return texto


def normalizar_ativo(valor: Any) -> str:
    texto = normalizar_sem_acentos(valor)
    if texto in {"S", "SIM", "TRUE", "1", "ATIVO"}:
        return "SIM"
    if texto in {"N", "NAO", "NÃO", "FALSE", "0", "INATIVO"}:
        return "NÃO"
    return "SIM"


def obter_link_planilha_configurada() -> str:
    config = obter_configuracao_sistema()
    link_planilha = str(config.get("planilha_google", "") or "").strip()

    if not link_planilha:
        raise ValueError("Nenhuma planilha Google vinculada foi encontrada nas configurações.")

    return link_planilha


def abrir_planilha(id_planilha: str | None = None):
    link_ou_id = str(id_planilha or "").strip() or obter_link_planilha_configurada()
    planilha, _ = abrir_planilha_e_base(link_ou_id)
    return planilha


def obter_ou_criar_aba_categorias(id_planilha: str | None = None):
    planilha = abrir_planilha(id_planilha)

    try:
        aba = planilha.worksheet(ABA_CATEGORIAS)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(
            title=ABA_CATEGORIAS,
            rows=max(len(CATEGORIAS_PADRAO) + 30, 100),
            cols=len(CABECALHOS_CATEGORIAS),
        )
        aba.update("A1:D1", [CABECALHOS_CATEGORIAS])
        aba.append_rows(CATEGORIAS_PADRAO, value_input_option="USER_ENTERED")
        return aba

    valores = aba.get_all_values()

    if not valores:
        aba.update("A1:D1", [CABECALHOS_CATEGORIAS])
        aba.append_rows(CATEGORIAS_PADRAO, value_input_option="USER_ENTERED")
    elif valores[0][: len(CABECALHOS_CATEGORIAS)] != CABECALHOS_CATEGORIAS:
        aba.update("A1:D1", [CABECALHOS_CATEGORIAS])

    return aba


def linha_para_categoria(linha: dict[str, Any]) -> dict[str, str]:
    tipo = normalizar_tipo(linha.get("TIPO"))
    categoria = normalizar_texto(linha.get("CATEGORIA"))
    subcategoria = normalizar_texto(linha.get("SUBCATEGORIA"))
    ativo = normalizar_ativo(linha.get("ATIVO"))

    return {
        "TIPO": tipo,
        "CATEGORIA": categoria,
        "SUBCATEGORIA": subcategoria,
        "ATIVO": ativo,
    }


def listar_categorias(
    incluir_inativas: bool = False,
    id_planilha: str | None = None,
) -> list[dict[str, str]]:
    aba = obter_ou_criar_aba_categorias(id_planilha)

    try:
        registros = aba.get_all_records()
    except Exception:
        registros = []

    categorias = []

    for linha in registros:
        item = linha_para_categoria(linha)

        if not item["TIPO"] or not item["CATEGORIA"]:
            continue

        if item["TIPO"] not in TIPOS_OFICIAIS:
            continue

        if not incluir_inativas and item["ATIVO"] != "SIM":
            continue

        categorias.append(item)

    return categorias


def obter_estrutura_categorias(
    incluir_inativas: bool = False,
    id_planilha: str | None = None,
) -> dict[str, dict[str, list[str]]]:
    estrutura: dict[str, dict[str, list[str]]] = {}

    for item in listar_categorias(incluir_inativas=incluir_inativas, id_planilha=id_planilha):
        tipo = item["TIPO"]
        categoria = item["CATEGORIA"]
        subcategoria = item["SUBCATEGORIA"]

        estrutura.setdefault(tipo, {})
        estrutura[tipo].setdefault(categoria, [])

        if subcategoria and subcategoria not in estrutura[tipo][categoria]:
            estrutura[tipo][categoria].append(subcategoria)

    for tipo in estrutura:
        estrutura[tipo] = dict(sorted(estrutura[tipo].items()))
        for categoria in estrutura[tipo]:
            estrutura[tipo][categoria] = sorted(estrutura[tipo][categoria])

    return estrutura


def obter_categorias_por_tipo(
    tipo: str,
    incluir_inativas: bool = False,
    id_planilha: str | None = None,
) -> dict[str, list[str]]:
    estrutura = obter_estrutura_categorias(
        incluir_inativas=incluir_inativas,
        id_planilha=id_planilha,
    )
    return estrutura.get(normalizar_tipo(tipo), {})


def resolver_categoria_subcategoria(
    tipo: str,
    categoria: str,
    subcategoria: str = "",
    incluir_inativas: bool = False,
    id_planilha: str | None = None,
) -> tuple[str, str, str]:
    tipo_norm = normalizar_tipo(tipo)
    categoria_norm = normalizar_texto(categoria)
    subcategoria_norm = normalizar_texto(subcategoria)

    estrutura = obter_estrutura_categorias(
        incluir_inativas=incluir_inativas,
        id_planilha=id_planilha,
    )

    if tipo_norm not in estrutura:
        raise ValueError(f"Tipo não cadastrado na aba CATEGORIAS: {tipo}")

    categorias_por_tipo = estrutura[tipo_norm]

    mapa_categorias = {
        normalizar_sem_acentos(cat): cat
        for cat in categorias_por_tipo.keys()
    }

    categoria_oficial = mapa_categorias.get(normalizar_sem_acentos(categoria_norm))

    if not categoria_oficial:
        raise ValueError(
            f"Categoria não cadastrada para {tipo_norm} na aba CATEGORIAS: {categoria}"
        )

    subcategorias = categorias_por_tipo.get(categoria_oficial, [])

    if not subcategorias:
        return tipo_norm, categoria_oficial, ""

    if not subcategoria_norm:
        raise ValueError(
            f"Informe uma subcategoria cadastrada para {tipo_norm}/{categoria_oficial}."
        )

    mapa_subcategorias = {
        normalizar_sem_acentos(sub): sub
        for sub in subcategorias
    }

    subcategoria_oficial = mapa_subcategorias.get(normalizar_sem_acentos(subcategoria_norm))

    if not subcategoria_oficial:
        raise ValueError(
            f"Subcategoria não cadastrada para {tipo_norm}/{categoria_oficial}: {subcategoria}"
        )

    return tipo_norm, categoria_oficial, subcategoria_oficial


def validar_categoria_subcategoria(
    tipo: str,
    categoria: str,
    subcategoria: str = "",
    id_planilha: str | None = None,
) -> tuple[str, str, str]:
    return resolver_categoria_subcategoria(
        tipo=tipo,
        categoria=categoria,
        subcategoria=subcategoria,
        incluir_inativas=False,
        id_planilha=id_planilha,
    )
