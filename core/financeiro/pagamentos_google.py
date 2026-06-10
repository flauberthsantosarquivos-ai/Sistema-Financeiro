"""
Módulo de Pagamentos - Sistema Financeiro

Arquivo:
core/financeiro/pagamentos_google.py

Funções principais:
- Cadastrar/editar pagamentos previstos na aba PAGAMENTOS.
- Listar pagamentos por filtros.
- Conferir pagamentos com a BASE_LANCAMENTOS.
- Usar categorias/subcategorias oficiais da aba CATEGORIAS.
- Corrigir exibição antiga de MATCH para nomes amigáveis.
"""

from __future__ import annotations

import re
import uuid
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import gspread

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.lancamentos_google import abrir_planilha_e_base
from core.financeiro.categorias_google import (
    obter_estrutura_categorias,
    validar_categoria_subcategoria as validar_categoria_subcategoria_oficial,
)


ABA_PAGAMENTOS = "PAGAMENTOS"

ABAS_LANCAMENTOS_CANDIDATAS = [
    "BASE_LANCAMENTOS",
    "LANÇAMENTOS",
    "LANCAMENTOS",
    "BASE",
    "DADOS_BRUTOS",
]

CABECALHO_PAGAMENTOS = [
    "ID",
    "ANO",
    "MES",
    "DESCRICAO",
    "TIPO",
    "CATEGORIA",
    "SUBCATEGORIA",
    "VALOR_PREVISTO",
    "VALOR_PAGO",
    "DATA_VENCIMENTO",
    "DATA_PAGAMENTO",
    "STATUS",
    "RECORRENTE",
    "CONTA_PAGAMENTO",
    "OBSERVACAO",
    "LANCAMENTO_ID",
    "LANCAMENTO_DATA",
    "LANCAMENTO_DESCRICAO",
    "LANCAMENTO_VALOR",
    "MATCH_STATUS",
    "MATCH_SCORE",
    "CRIADO_EM",
    "ATUALIZADO_EM",
]

STATUS_PAGAMENTO = [
    "PENDENTE",
    "PAGO",
    "ATRASADO",
    "VENCE HOJE",
    "POSSÍVEL PAGAMENTO",
    "PARCIAL",
    "CANCELADO",
]

MESES_ORDEM = [
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

MESES_NUMERO = {mes: i + 1 for i, mes in enumerate(MESES_ORDEM)}

CATEGORIAS_PADRAO = {
    "DESPESA": {
        "MORADIA": [
            "PRESTAÇÃO AP",
            "CONDOMÍNIO",
            "ENERGIA",
            "ÁGUA",
            "INTERNET",
            "IPTU",
        ],
        "ALIMENTAÇÃO": [
            "SUPERMERCADO",
            "PADARIA",
            "RESTAURANTE",
        ],
        "TRANSPORTE": [
            "COMBUSTÍVEL",
            "UBER",
            "MANUTENÇÃO",
        ],
        "SAÚDE": [
            "PLANO DE SAÚDE",
            "FARMÁCIA",
            "CONSULTAS",
        ],
        "CARTÃO": [
            "FATURA CARTÃO",
        ],
        "EDUCAÇÃO": [
            "ESCOLA",
            "CURSO",
            "MATERIAL",
        ],
        "SERVIÇOS": [
            "TELEFONE",
            "STREAMING",
            "ASSINATURAS",
        ],
    },
    "RECEITA": {
        "SALÁRIO": [
            "SALÁRIO PRINCIPAL",
            "ADIANTAMENTO",
            "OUTRAS RECEITAS",
        ],
        "RENDIMENTOS": [
            "JUROS",
            "DIVIDENDOS",
            "OUTROS RENDIMENTOS",
        ],
    },
    "INVESTIMENTO": {
        "RESERVA": [
            "TESOURO",
            "CDB",
            "POUPANÇA",
            "FUNDO",
        ],
    },
    "TRANSFERÊNCIA": {
        "CONTAS PRÓPRIAS": [
            "TRANSFERÊNCIA ENTRE CONTAS",
            "APORTE",
            "RESGATE",
        ],
    },
}


# Subcategorias que normalmente aparecem em vários lançamentos no mês.
# Para estas, a conferência de Pagamentos deve somar todos os lançamentos
# compatíveis da BASE_LANCAMENTOS por mês + categoria + subcategoria.
# As demais continuam usando a regra antiga de melhor lançamento individual.
SUBCATEGORIAS_CONCILIACAO_POR_SOMA = {
    "SUPERMERCADO",
    "RESTAURANTE",
    "FLV",
    "PADARIA",
    "FARMACIA",
    "COMBUSTIVEL",
    "UBER",
    "MANUTENCAO",
}

CATEGORIAS_CONCILIACAO_POR_SOMA = {
    ("ALIMENTACAO", "SUPERMERCADO"),
    ("ALIMENTACAO", "RESTAURANTE"),
    ("ALIMENTACAO", "FLV"),
    ("ALIMENTACAO", "PADARIA"),
    ("SAUDE", "FARMACIA"),
    ("TRANSPORTE", "COMBUSTIVEL"),
    ("TRANSPORTE", "UBER"),
    ("TRANSPORTE", "MANUTENCAO"),
}


def agora_iso() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().upper()
    mapa = str.maketrans(
        "ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
        "AAAAAEEEEIIIIOOOOOUUUUC",
    )
    texto = texto.translate(mapa)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def normalizar_status_lancamento(status: Any) -> str:
    texto = normalizar_texto(status)

    mapa = {
        "MATCH FORTE": "PAGAMENTO ENCONTRADO",
        "MATCH POSSIVEL": "POSSÍVEL LANÇAMENTO",
        "MATCH POSSÍVEL": "POSSÍVEL LANÇAMENTO",
        "MATCH PARCIAL": "PAGAMENTO PARCIAL",
        "SEM VINCULO": "NÃO ENCONTRADO",
        "SEM VÍNCULO": "NÃO ENCONTRADO",
        "CONCILIADO AUTOMATICAMENTE": "PAGAMENTO ENCONTRADO",
        "SUGESTAO DE CONCILIACAO": "POSSÍVEL LANÇAMENTO",
        "SUGESTÃO DE CONCILIAÇÃO": "POSSÍVEL LANÇAMENTO",
    }

    if not texto:
        return ""

    return mapa.get(texto, str(status or "").strip())


def parse_moeda(valor: Any) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "").replace("\xa0", "")

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", "")

    try:
        return float(texto)
    except ValueError:
        return 0.0


def formatar_moeda(valor: Any) -> str:
    numero = parse_moeda(valor)
    texto = f"{numero:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def parse_data(valor: Any) -> Optional[date]:
    if isinstance(valor, date):
        return valor

    texto = str(valor or "").strip()
    if not texto:
        return None

    formatos = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass

    return None


def formatar_data(data_valor: Optional[date]) -> str:
    if not data_valor:
        return ""
    return data_valor.strftime("%d/%m/%Y")


def mes_para_numero(mes: Any) -> Optional[int]:
    texto = normalizar_texto(mes)

    if texto in MESES_NUMERO:
        return MESES_NUMERO[texto]

    try:
        numero = int(str(mes).strip())
        if 1 <= numero <= 12:
            return numero
    except Exception:
        return None

    return None


def mes_numero_para_sigla(numero: int) -> str:
    if 1 <= numero <= 12:
        return MESES_ORDEM[numero - 1]
    return ""


def obter_link_planilha_configurada() -> str:
    config = obter_configuracao_sistema()
    link_planilha = str(config.get("planilha_google", "") or "").strip()

    if not link_planilha:
        raise ValueError(
            "Nenhuma planilha Google vinculada foi encontrada nas configurações."
        )

    return link_planilha


def abrir_planilha(id_planilha: Optional[str] = None):
    link_ou_id = str(id_planilha or "").strip() or obter_link_planilha_configurada()
    planilha, _aba_base_ignorada = abrir_planilha_e_base(link_ou_id)
    return planilha


def obter_ou_criar_aba(planilha, nome: str, cabecalho: Optional[List[str]] = None):
    try:
        aba = planilha.worksheet(nome)
    except gspread.WorksheetNotFound:
        colunas = max(len(cabecalho or []), 10)
        aba = planilha.add_worksheet(title=nome, rows=1000, cols=colunas)

    if cabecalho:
        valores = aba.get_all_values()
        primeira_linha = valores[0] if valores else []

        if primeira_linha != cabecalho:
            aba.resize(rows=max(len(valores), 1) + 20, cols=len(cabecalho))
            aba.update("A1", [cabecalho])

    return aba


def garantir_estrutura_pagamentos(id_planilha: Optional[str] = None):
    planilha = abrir_planilha(id_planilha)
    aba = obter_ou_criar_aba(planilha, ABA_PAGAMENTOS, CABECALHO_PAGAMENTOS)
    return planilha, aba


def linha_para_dict(cabecalho: List[str], linha: List[Any]) -> Dict[str, Any]:
    item = {}
    for idx, coluna in enumerate(cabecalho):
        item[coluna] = linha[idx] if idx < len(linha) else ""
    return item


def ler_aba_como_dicts(aba) -> List[Dict[str, Any]]:
    valores = aba.get_all_values()
    if not valores:
        return []

    cabecalho = valores[0]
    linhas = valores[1:]
    return [
        linha_para_dict(cabecalho, linha)
        for linha in linhas
        if any(str(c).strip() for c in linha)
    ]


def obter_opcoes_categorias(id_planilha: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna a estrutura oficial da aba CATEGORIAS.

    A partir da padronização da Etapa 3, o módulo Pagamentos não usa mais
    listas internas/fallback para cadastrar ou editar pagamentos. A fonte única
    é a aba CATEGORIAS.
    """
    estrutura = obter_estrutura_categorias(
        incluir_inativas=False,
        id_planilha=id_planilha,
    )

    if not estrutura:
        raise ValueError(
            "Nenhuma categoria ativa foi encontrada na aba CATEGORIAS. "
            "Cadastre ao menos uma combinação TIPO/CATEGORIA/SUBCATEGORIA ativa."
        )

    return estrutura


def resolver_categoria_na_estrutura(
    tipo: str,
    categoria: str,
    subcategoria: str,
    estrutura: Dict[str, Any],
) -> Tuple[str, str, str]:
    """
    Resolve uma combinação usando a estrutura já carregada da aba CATEGORIAS.

    Usado principalmente na duplicação mensal para evitar várias leituras
    repetidas no Google Sheets.
    """
    tipo_norm = normalizar_texto(tipo)
    categoria_norm = normalizar_texto(categoria)
    subcategoria_norm = normalizar_texto(subcategoria)

    if tipo_norm == "TRANSFERENCIA":
        tipo_norm = "TRANSFERÊNCIA"

    if tipo_norm not in estrutura:
        raise ValueError(f"Tipo não cadastrado na aba CATEGORIAS: {tipo}")

    categorias_tipo = estrutura[tipo_norm]

    mapa_categorias = {
        normalizar_texto(nome): nome
        for nome in categorias_tipo.keys()
    }

    categoria_oficial = mapa_categorias.get(categoria_norm)

    if not categoria_oficial:
        raise ValueError(
            f"Categoria não cadastrada para {tipo_norm} na aba CATEGORIAS: {categoria}"
        )

    subcategorias = categorias_tipo.get(categoria_oficial, [])

    if not subcategorias:
        return tipo_norm, categoria_oficial, ""

    if not subcategoria_norm:
        raise ValueError(
            f"Informe uma subcategoria cadastrada para {tipo_norm}/{categoria_oficial}."
        )

    mapa_subcategorias = {
        normalizar_texto(nome): nome
        for nome in subcategorias
    }

    subcategoria_oficial = mapa_subcategorias.get(subcategoria_norm)

    if not subcategoria_oficial:
        raise ValueError(
            f"Subcategoria não cadastrada para {tipo_norm}/{categoria_oficial}: {subcategoria}"
        )

    return tipo_norm, categoria_oficial, subcategoria_oficial


def validar_categoria_subcategoria(
    tipo: str,
    categoria: str,
    subcategoria: str,
    id_planilha: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Valida sempre contra a aba oficial CATEGORIAS.

    Não há mais fallback de categorias antigas dentro do módulo Pagamentos.
    """
    return validar_categoria_subcategoria_oficial(
        tipo,
        categoria,
        subcategoria,
        id_planilha=id_planilha,
    )


def status_por_vencimento(data_vencimento: Optional[date], status_atual: str) -> str:
    status_norm = normalizar_texto(status_atual)

    if status_norm in {
        "PAGO",
        "CANCELADO",
        "PARCIAL",
        "POSSIVEL PAGAMENTO",
        "POSSÍVEL PAGAMENTO",
    }:
        return status_atual or status_norm

    hoje = date.today()

    if not data_vencimento:
        return "PENDENTE"

    if data_vencimento < hoje:
        return "ATRASADO"

    if data_vencimento == hoje:
        return "VENCE HOJE"

    return "PENDENTE"


def grupo_vencimento(data_vencimento: Optional[date]) -> str:
    if not data_vencimento:
        return "SEM DATA"

    if data_vencimento.day <= 15:
        return "INÍCIO DO MÊS"

    return "FINAL DO MÊS"


def preparar_pagamento_para_tela(item: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(item)

    valor_previsto = parse_moeda(item.get("VALOR_PREVISTO"))
    valor_pago = parse_moeda(item.get("VALOR_PAGO"))
    data_vencimento = parse_data(item.get("DATA_VENCIMENTO"))
    data_pagamento = parse_data(item.get("DATA_PAGAMENTO"))

    status = status_por_vencimento(data_vencimento, item.get("STATUS") or "PENDENTE")
    status_norm = normalizar_texto(status)

    item["VALOR_PREVISTO_NUM"] = valor_previsto
    item["VALOR_PAGO_NUM"] = valor_pago
    item["VALOR_PREVISTO_FMT"] = formatar_moeda(valor_previsto)
    item["VALOR_PAGO_FMT"] = formatar_moeda(valor_pago)
    item["DATA_VENCIMENTO_FMT"] = formatar_data(data_vencimento)
    item["DATA_PAGAMENTO_FMT"] = formatar_data(data_pagamento)
    item["STATUS_CALCULADO"] = status
    item["GRUPO_VENCIMENTO"] = grupo_vencimento(data_vencimento)
    item["MATCH_STATUS"] = normalizar_status_lancamento(item.get("MATCH_STATUS", ""))

    # Regra de apresentação: se o pagamento está pago, a situação da conferência
    # deve aparecer como PAGAMENTO ENCONTRADO, mesmo que a planilha ainda tenha
    # guardado POSSÍVEL LANÇAMENTO de uma conferência anterior.
    if status_norm == "PAGO":
        item["MATCH_STATUS"] = "PAGAMENTO ENCONTRADO"

    item["MATCH_SCORE_NUM"] = parse_moeda(item.get("MATCH_SCORE"))

    return item


def pagamento_passa_filtros(item: Dict[str, Any], filtros: Dict[str, Any]) -> bool:
    ano = str(filtros.get("ano") or "").strip()
    mes = str(filtros.get("mes") or "").strip()
    status = normalizar_texto(filtros.get("status"))
    tipo = normalizar_texto(filtros.get("tipo"))
    categoria = normalizar_texto(filtros.get("categoria"))

    if ano and str(item.get("ANO") or "").strip() != ano:
        return False

    if mes and normalizar_texto(item.get("MES")) != normalizar_texto(mes):
        return False

    if status and normalizar_texto(item.get("STATUS_CALCULADO") or item.get("STATUS")) != status:
        return False

    if tipo and normalizar_texto(item.get("TIPO")) != tipo:
        return False

    if categoria and normalizar_texto(item.get("CATEGORIA")) != categoria:
        return False

    return True


def listar_pagamentos(
    filtros: Optional[Dict[str, Any]] = None,
    id_planilha: Optional[str] = None,
) -> List[Dict[str, Any]]:
    filtros = filtros or {}
    _, aba = garantir_estrutura_pagamentos(id_planilha)
    dados = ler_aba_como_dicts(aba)

    preparados = [preparar_pagamento_para_tela(item) for item in dados]
    filtrados = [item for item in preparados if pagamento_passa_filtros(item, filtros)]

    def chave_ordenacao(item):
        data_venc = parse_data(item.get("DATA_VENCIMENTO")) or date(9999, 12, 31)
        return (
            str(item.get("ANO") or ""),
            MESES_NUMERO.get(normalizar_texto(item.get("MES")), 99),
            data_venc,
            normalizar_texto(item.get("CATEGORIA")),
            normalizar_texto(item.get("SUBCATEGORIA")),
        )

    return sorted(filtrados, key=chave_ordenacao)


def salvar_pagamento(dados: Dict[str, Any], id_planilha: Optional[str] = None) -> Dict[str, Any]:
    _, aba = garantir_estrutura_pagamentos(id_planilha)

    pagamento_id = str(dados.get("ID") or dados.get("id") or "").strip()
    criando = not pagamento_id

    if criando:
        pagamento_id = str(uuid.uuid4())

    tipo, categoria, subcategoria = validar_categoria_subcategoria(
        dados.get("TIPO") or dados.get("tipo") or "DESPESA",
        dados.get("CATEGORIA") or dados.get("categoria") or "",
        dados.get("SUBCATEGORIA") or dados.get("subcategoria") or "",
        id_planilha=id_planilha,
    )

    data_vencimento = parse_data(dados.get("DATA_VENCIMENTO") or dados.get("data_vencimento"))
    data_pagamento = parse_data(dados.get("DATA_PAGAMENTO") or dados.get("data_pagamento"))

    ano = str(dados.get("ANO") or dados.get("ano") or "")
    mes = normalizar_texto(dados.get("MES") or dados.get("mes") or "")

    if not ano and data_vencimento:
        ano = str(data_vencimento.year)

    if not mes and data_vencimento:
        mes = mes_numero_para_sigla(data_vencimento.month)

    status = normalizar_texto(dados.get("STATUS") or dados.get("status") or "PENDENTE")

    if status not in [normalizar_texto(s) for s in STATUS_PAGAMENTO]:
        status = "PENDENTE"

    registro = {
        "ID": pagamento_id,
        "ANO": ano,
        "MES": mes,
        "DESCRICAO": str(dados.get("DESCRICAO") or dados.get("descricao") or "").strip(),
        "TIPO": tipo,
        "CATEGORIA": categoria,
        "SUBCATEGORIA": subcategoria,
        "VALOR_PREVISTO": formatar_moeda(dados.get("VALOR_PREVISTO") or dados.get("valor_previsto") or 0),
        "VALOR_PAGO": formatar_moeda(dados.get("VALOR_PAGO") or dados.get("valor_pago") or 0),
        "DATA_VENCIMENTO": formatar_data(data_vencimento),
        "DATA_PAGAMENTO": formatar_data(data_pagamento),
        "STATUS": status,
        "RECORRENTE": normalizar_texto(dados.get("RECORRENTE") or dados.get("recorrente") or "NÃO"),
        "CONTA_PAGAMENTO": str(dados.get("CONTA_PAGAMENTO") or dados.get("conta_pagamento") or "").strip(),
        "OBSERVACAO": str(dados.get("OBSERVACAO") or dados.get("observacao") or "").strip(),
        "LANCAMENTO_ID": str(dados.get("LANCAMENTO_ID") or "").strip(),
        "LANCAMENTO_DATA": str(dados.get("LANCAMENTO_DATA") or "").strip(),
        "LANCAMENTO_DESCRICAO": str(dados.get("LANCAMENTO_DESCRICAO") or "").strip(),
        "LANCAMENTO_VALOR": str(dados.get("LANCAMENTO_VALOR") or "").strip(),
        "MATCH_STATUS": str(dados.get("MATCH_STATUS") or "").strip(),
        "MATCH_SCORE": str(dados.get("MATCH_SCORE") or "").strip(),
        "CRIADO_EM": str(dados.get("CRIADO_EM") or agora_iso()).strip(),
        "ATUALIZADO_EM": agora_iso(),
    }

    valores = aba.get_all_values()
    linha_final = [registro.get(coluna, "") for coluna in CABECALHO_PAGAMENTOS]

    if criando:
        aba.append_row(linha_final, value_input_option="USER_ENTERED")
    else:
        indice_linha = None
        for idx, linha in enumerate(valores[1:], start=2):
            if linha and str(linha[0]).strip() == pagamento_id:
                indice_linha = idx
                break

        if indice_linha:
            aba.update(f"A{indice_linha}", [linha_final], value_input_option="USER_ENTERED")
        else:
            aba.append_row(linha_final, value_input_option="USER_ENTERED")

    return preparar_pagamento_para_tela(registro)


def atualizar_status_pagamento(
    pagamento_id: str,
    status: str,
    valor_pago: Optional[Any] = None,
    data_pagamento: Optional[Any] = None,
    id_planilha: Optional[str] = None,
) -> bool:
    _, aba = garantir_estrutura_pagamentos(id_planilha)
    valores = aba.get_all_values()

    if not valores:
        return False

    cabecalho = valores[0]
    status_norm = normalizar_texto(status)

    try:
        idx_status = cabecalho.index("STATUS")
        idx_valor_pago = cabecalho.index("VALOR_PAGO")
        idx_data_pagamento = cabecalho.index("DATA_PAGAMENTO")
        idx_match_status = cabecalho.index("MATCH_STATUS") if "MATCH_STATUS" in cabecalho else None
        idx_match_score = cabecalho.index("MATCH_SCORE") if "MATCH_SCORE" in cabecalho else None
        idx_atualizado = cabecalho.index("ATUALIZADO_EM")
    except ValueError:
        return False

    for idx, linha in enumerate(valores[1:], start=2):
        if linha and str(linha[0]).strip() == pagamento_id:
            while len(linha) < len(cabecalho):
                linha.append("")

            linha[idx_status] = status_norm

            if status_norm == "PAGO" and idx_match_status is not None:
                linha[idx_match_status] = "PAGAMENTO ENCONTRADO"

            if status_norm == "PAGO" and idx_match_score is not None:
                linha[idx_match_score] = "MANUAL"

            if valor_pago is not None:
                linha[idx_valor_pago] = formatar_moeda(valor_pago)

            if data_pagamento is not None:
                linha[idx_data_pagamento] = formatar_data(parse_data(data_pagamento))

            linha[idx_atualizado] = agora_iso()
            aba.update(f"A{idx}", [linha], value_input_option="USER_ENTERED")
            return True

    return False


def encontrar_aba_lancamentos(planilha):
    for nome in ABAS_LANCAMENTOS_CANDIDATAS:
        try:
            return planilha.worksheet(nome)
        except Exception:
            pass
    return None


def obter_campo(item: Dict[str, Any], nomes: List[str]) -> Any:
    nomes_norm = [normalizar_texto(n) for n in nomes]

    for chave, valor in item.items():
        if normalizar_texto(chave) in nomes_norm:
            return valor

    return ""


def normalizar_categoria_match(valor: Any) -> str:
    texto = normalizar_texto(valor)

    # A categoria oficial atual é CASA. MORADIA é mantida apenas como alias
    # para compatibilizar pagamentos/lancamentos antigos.
    aliases = {
        "CASA": "CASA",
        "MORADIA": "CASA",
        "ALIMENTACAO": "ALIMENTACAO",
        "ALIMENTAÇÃO": "ALIMENTACAO",
        "TRANSPORTE": "TRANSPORTE",
        "SAUDE": "SAUDE",
        "SAÚDE": "SAUDE",
        "EDUCACAO": "EDUCACAO",
        "EDUCAÇÃO": "EDUCACAO",
        "SERVICOS": "SERVICOS",
        "SERVIÇOS": "SERVICOS",
        "CARTAO": "CARTAO",
        "CARTÃO": "CARTAO",
        "INVESTIMENTO": "INVESTIMENTO",
        "TRANSFERENCIA": "TRANSFERENCIA",
        "TRANSFERÊNCIA": "TRANSFERENCIA",
        "OUTROS": "OUTROS",
    }

    return aliases.get(texto, texto)


def normalizar_subcategoria_match(
    categoria: Any,
    subcategoria: Any,
    descricao: Any = "",
) -> str:
    categoria_n = normalizar_categoria_match(categoria)
    sub_n = normalizar_texto(subcategoria)
    desc_n = normalizar_texto(descricao)
    texto = f"{sub_n} {desc_n}"

    if categoria_n == "ALIMENTACAO":
        if any(p in texto for p in ["FLV", "FRUTA", "FRUTAS", "LEGUME", "LEGUMES", "VERDURA", "VERDURAS", "HORTIFRUTI", "HORTI FRUTI"]):
            return "FLV"
        if any(p in texto for p in ["SUPERMERCADO", "SUPER MERCADO", "MERCADO", "ATACADAO", "ATACADÃO", "ASSAI", "ASSAÍ", "MATEUS", "CARREFOUR", "EXTRA"]):
            return "SUPERMERCADO"
        if any(p in texto for p in ["RESTAURANTE", "LANCHONETE", "IFOOD", "DELIVERY", "PIZZARIA", "PADARIA"]):
            return "RESTAURANTE" if "PADARIA" not in texto else "PADARIA"

    if categoria_n == "TRANSPORTE":
        if any(p in texto for p in ["COMBUSTIVEL", "COMBUSTÍVEL", "GASOLINA", "ETANOL", "POSTO", "SHELL", "IPIRANGA", "RAIZEN", "BR "]):
            return "COMBUSTIVEL"
        if any(p in texto for p in ["UBER", "99", "MOBI", "CORRIDA"]):
            return "UBER"

    if categoria_n == "CASA":
        if any(p in texto for p in ["ENERGIA", "ENERGIA ELETRICA", "ENERGIA ELÉTRICA", "EQUATORIAL", "CEMAR", "LUZ"]):
            return "ENERGIA"
        if any(p in texto for p in ["CONDOMINIO", "CONDOMÍNIO"]):
            return "CONDOMINIO"
        if any(p in texto for p in ["PRESTACAO AP", "PRESTAÇÃO AP", "PRESTACAO", "PRESTAÇÃO", "FINANCIAMENTO", "CAIXA HAB", "HABITACAO", "HABITAÇÃO"]):
            return "PRESTACAO AP"
        if any(p in texto for p in ["AMORTIZACAO", "AMORTIZAÇÃO"]):
            return "AMORTIZACAO"
        if any(p in texto for p in ["AGUA", "ÁGUA"]):
            return "AGUA"
        if "INTERNET" in texto:
            return "INTERNET"

    if categoria_n == "SAUDE":
        if any(p in texto for p in ["FARMACIA", "FARMÁCIA", "DROGARIA", "MEDICAMENTO", "REMEDIO", "REMÉDIO"]):
            return "FARMACIA"
        if any(p in texto for p in ["PLANO DE SAUDE", "PLANO DE SAÚDE", "UNIMED", "HAPVIDA"]):
            return "PLANO DE SAUDE"

    if categoria_n == "EDUCACAO":
        if any(p in texto for p in ["ESCOLA", "ISAAC", "MENSALIDADE"]):
            return "ESCOLA"

    return sub_n


def pagamento_variavel_para_match(pagamento: Dict[str, Any]) -> bool:
    categoria = normalizar_categoria_match(pagamento.get("CATEGORIA"))
    sub = normalizar_subcategoria_match(
        pagamento.get("CATEGORIA"),
        pagamento.get("SUBCATEGORIA"),
        pagamento.get("DESCRICAO"),
    )
    desc = normalizar_texto(pagamento.get("DESCRICAO"))
    texto = f"{categoria} {sub} {desc}"

    termos_variaveis = [
        "COMBUSTIVEL",
        "SUPERMERCADO",
        "FLV",
        "RESTAURANTE",
        "PADARIA",
        "FARMACIA",
        "UBER",
        "MANUTENCAO",
        "MANUTENÇÃO",
    ]

    return any(termo in texto for termo in termos_variaveis)



def pagamento_deve_conciliar_por_soma(pagamento: Dict[str, Any]) -> bool:
    """
    Define se um pagamento previsto deve ser conferido por soma mensal.

    Importante: esta decisão usa a categoria/subcategoria cadastrada no próprio
    pagamento. Não usa palavras da descrição para evitar que descrições como
    "posto" transformem despesas de outra subcategoria em combustível.
    """
    categoria = normalizar_categoria_match(pagamento.get("CATEGORIA"))
    subcategoria = normalizar_texto(pagamento.get("SUBCATEGORIA"))

    if (categoria, subcategoria) in CATEGORIAS_CONCILIACAO_POR_SOMA:
        return True

    return subcategoria in SUBCATEGORIAS_CONCILIACAO_POR_SOMA


def lancamento_pertence_ao_mes_pagamento(
    pagamento: Dict[str, Any],
    lancamento: Dict[str, Any],
) -> bool:
    """Confere se o lançamento pertence ao mesmo ano/mês do pagamento."""
    data_lanc = lancamento.get("DATA")

    if not data_lanc:
        return False

    ano_pag = str(pagamento.get("ANO") or "").strip()
    mes_pag = mes_para_numero(pagamento.get("MES"))

    if ano_pag and str(data_lanc.year) != ano_pag:
        return False

    if mes_pag and data_lanc.month != mes_pag:
        return False

    return True


def lancamento_tem_mes_compatível_para_match_individual(
    pagamento: Dict[str, Any],
    lancamento: Dict[str, Any],
) -> bool:
    """
    Mantém a regra anterior do match individual: prioriza o mesmo mês,
    mas aceita poucos dias de diferença quando a data de vencimento justificar.
    """
    data_lanc = lancamento.get("DATA")

    if not data_lanc:
        return True

    ano_pag = str(pagamento.get("ANO") or "")
    mes_pag = mes_para_numero(pagamento.get("MES"))

    if ano_pag and str(data_lanc.year) != ano_pag:
        return False

    if mes_pag and data_lanc.month != mes_pag:
        data_venc = parse_data(pagamento.get("DATA_VENCIMENTO"))
        if not data_venc or abs((data_lanc - data_venc).days) > 7:
            return False

    return True


def lancamento_tem_categoria_subcategoria_do_pagamento(
    pagamento: Dict[str, Any],
    lancamento: Dict[str, Any],
) -> bool:
    """
    Comparação estrita para conciliação por soma.

    Aqui a regra correta é respeitar a classificação que já está gravada na
    BASE_LANCAMENTOS. A descrição do lançamento não deve reclassificar nada.
    Exemplo: compra em POSTO classificada na Base como ADITIVO não pode entrar
    na soma de COMBUSTÍVEL apenas porque a descrição contém "posto".
    """
    cat_pag = normalizar_categoria_match(pagamento.get("CATEGORIA"))
    sub_pag = normalizar_texto(pagamento.get("SUBCATEGORIA"))

    cat_lanc = normalizar_categoria_match(lancamento.get("CATEGORIA"))
    sub_lanc = normalizar_texto(lancamento.get("SUBCATEGORIA"))

    return bool(
        cat_pag
        and cat_lanc
        and cat_pag == cat_lanc
        and sub_pag
        and sub_lanc
        and sub_pag == sub_lanc
    )


def resumir_lancamentos_somados(lancamentos: List[Dict[str, Any]]) -> str:
    if not lancamentos:
        return ""

    partes = []
    for lanc in lancamentos[:4]:
        data_txt = formatar_data(lanc.get("DATA"))
        desc_txt = str(lanc.get("DESCRICAO") or "").strip()
        valor_txt = formatar_moeda(lanc.get("VALOR"))
        trecho = " - ".join([p for p in [data_txt, desc_txt, valor_txt] if p])
        if trecho:
            partes.append(trecho)

    if len(lancamentos) > 4:
        partes.append(f"+ {len(lancamentos) - 4} lançamento(s)")

    return " | ".join(partes)


def conciliar_pagamento_por_soma(
    pagamento: Dict[str, Any],
    lancamentos: List[Dict[str, Any]],
    usados_lancamentos: set,
) -> Optional[Dict[str, Any]]:
    """
    Concilia despesas variáveis somando todos os lançamentos do mês
    com a mesma categoria/subcategoria.
    """
    lancamentos_compativeis = []

    for lanc in lancamentos:
        if lanc.get("ID") in usados_lancamentos:
            continue

        if not lancamento_pertence_ao_mes_pagamento(pagamento, lanc):
            continue

        if not lancamento_tem_categoria_subcategoria_do_pagamento(pagamento, lanc):
            continue

        valor_lanc = parse_moeda(lanc.get("VALOR"))
        if valor_lanc <= 0:
            continue

        lancamentos_compativeis.append(lanc)

    if not lancamentos_compativeis:
        return None

    valor_previsto = parse_moeda(pagamento.get("VALOR_PREVISTO"))
    total_pago = sum(parse_moeda(lanc.get("VALOR")) for lanc in lancamentos_compativeis)
    diferenca = valor_previsto - total_pago

    if valor_previsto > 0 and total_pago + 1 >= valor_previsto:
        novo_status = "PAGO"
        match_status = "PAGAMENTO ENCONTRADO"
        tipo_resultado = "atualizado"
    elif total_pago > 0:
        novo_status = "PARCIAL"
        match_status = "PAGAMENTO PARCIAL"
        tipo_resultado = "parcial"
    else:
        return None

    datas_validas = [lanc.get("DATA") for lanc in lancamentos_compativeis if lanc.get("DATA")]
    data_pagamento = max(datas_validas) if datas_validas else None

    return {
        "novo_status": novo_status,
        "match_status": match_status,
        "match_score": f"SOMA:{len(lancamentos_compativeis)}",
        "tipo_resultado": tipo_resultado,
        "valor_pago": total_pago,
        "data_pagamento": data_pagamento,
        "lancamento_id": ", ".join(str(lanc.get("ID") or "") for lanc in lancamentos_compativeis),
        "lancamento_data": formatar_data(data_pagamento),
        "lancamento_descricao": resumir_lancamentos_somados(lancamentos_compativeis),
        "lancamento_valor": total_pago,
        "lancamentos": lancamentos_compativeis,
        "motivos": [
            "conciliação por soma mensal",
            "categoria/subcategoria compatível",
            f"{len(lancamentos_compativeis)} lançamento(s) somado(s)",
            f"diferença: {formatar_moeda(max(diferenca, 0))}",
        ],
    }

def normalizar_lancamento(item: Dict[str, Any], indice: int) -> Dict[str, Any]:
    data_raw = obter_campo(item, ["DATA", "DATA_LANCAMENTO", "DATA LANÇAMENTO", "DATA DO LANÇAMENTO"])
    descricao = obter_campo(item, ["DESCRICAO", "DESCRIÇÃO", "HISTORICO", "HISTÓRICO", "LANÇAMENTO", "LANCAMENTO", "DETALHES"])
    tipo = obter_campo(item, ["TIPO", "TIPO_LANCAMENTO", "TIPO LANÇAMENTO", "NATUREZA"])
    categoria = obter_campo(item, ["CATEGORIA", "CATEGORIA_AJUSTADA", "CATEGORIA AJUSTADA"])
    subcategoria = obter_campo(item, ["SUBCATEGORIA", "SUB CATEGORIA", "SUB_CATEGORIA", "SUBCATEGORIA_AJUSTADA", "SUBCATEGORIA AJUSTADA"])
    valor = obter_campo(item, ["VALOR", "VALOR_NUM", "VALOR REALIZADO", "VALOR_REALIZADO", "VALOR_LANCAMENTO", "VALOR LANÇAMENTO"])
    conta = obter_campo(item, ["CONTA", "CONTA_PAGAMENTO", "BANCO"])

    lancamento_id = obter_campo(item, ["ID", "LANCAMENTO_ID", "ID_LANCAMENTO"]) or f"LINHA-{indice}"
    categoria_match = normalizar_categoria_match(categoria)
    subcategoria_match = normalizar_subcategoria_match(categoria, subcategoria, descricao)

    return {
        "ID": str(lancamento_id),
        "DATA": parse_data(data_raw),
        "DATA_RAW": str(data_raw or ""),
        "DESCRICAO": str(descricao or ""),
        "TIPO": normalizar_texto(tipo),
        "CATEGORIA": normalizar_texto(categoria),
        "SUBCATEGORIA": normalizar_texto(subcategoria),
        "CATEGORIA_MATCH": categoria_match,
        "SUBCATEGORIA_MATCH": subcategoria_match,
        "VALOR": abs(parse_moeda(valor)),
        "VALOR_RAW": valor,
        "CONTA": str(conta or ""),
        "ORIGINAL": item,
    }


def listar_lancamentos_normalizados(id_planilha: Optional[str] = None) -> List[Dict[str, Any]]:
    planilha = abrir_planilha(id_planilha)
    aba = encontrar_aba_lancamentos(planilha)

    if not aba:
        return []

    dados = ler_aba_como_dicts(aba)
    return [normalizar_lancamento(item, idx) for idx, item in enumerate(dados, start=2)]


def calcular_score_match(pagamento: Dict[str, Any], lancamento: Dict[str, Any]) -> Tuple[int, List[str]]:
    motivos: List[str] = []
    score = 0

    cat_pag = normalizar_categoria_match(pagamento.get("CATEGORIA"))
    sub_pag = normalizar_subcategoria_match(
        pagamento.get("CATEGORIA"),
        pagamento.get("SUBCATEGORIA"),
        pagamento.get("DESCRICAO"),
    )
    desc_pag = normalizar_texto(pagamento.get("DESCRICAO"))

    cat_lanc = normalizar_categoria_match(
        lancamento.get("CATEGORIA_MATCH") or lancamento.get("CATEGORIA")
    )
    sub_lanc = normalizar_texto(
        lancamento.get("SUBCATEGORIA_MATCH") or lancamento.get("SUBCATEGORIA")
    )
    desc_lanc = normalizar_texto(lancamento.get("DESCRICAO"))

    valor_previsto = parse_moeda(pagamento.get("VALOR_PREVISTO"))
    valor_lanc = parse_moeda(lancamento.get("VALOR"))
    data_vencimento = parse_data(pagamento.get("DATA_VENCIMENTO"))
    despesa_variavel = pagamento_variavel_para_match(pagamento)

    if cat_pag and cat_lanc and cat_pag == cat_lanc:
        score += 35
        motivos.append("categoria compatível")

    if sub_pag and sub_lanc and sub_pag == sub_lanc:
        score += 45
        motivos.append("subcategoria compatível")

    texto_pagamento = f"{cat_pag} {sub_pag} {desc_pag}"
    texto_lancamento = f"{cat_lanc} {sub_lanc} {desc_lanc}"

    termos_fortes = [
        "COMBUSTIVEL",
        "GASOLINA",
        "ETANOL",
        "POSTO",
        "ENERGIA",
        "EQUATORIAL",
        "CEMAR",
        "LUZ",
        "FLV",
        "SUPERMERCADO",
        "MERCADO",
        "CONDOMINIO",
        "PRESTACAO",
        "AMORTIZACAO",
        "FARMACIA",
    ]

    for termo in termos_fortes:
        if termo in texto_pagamento and termo in texto_lancamento:
            score += 12
            motivos.append(f"termo forte: {termo}")
            break

    diferenca_valor = abs(valor_previsto - valor_lanc)

    if valor_previsto > 0 and valor_lanc > 0:
        percentual_diferenca = diferenca_valor / valor_previsto * 100

        if diferenca_valor <= 1:
            score += 35
            motivos.append("valor igual/próximo")
        elif percentual_diferenca <= 5:
            score += 20
            motivos.append("valor próximo")
        elif despesa_variavel and valor_lanc < valor_previsto:
            score += 8
            motivos.append("lançamento parcial de despesa variável")
        elif valor_lanc < valor_previsto and percentual_diferenca <= 40:
            score += 6
            motivos.append("possível pagamento menor que o previsto")
        elif sub_pag and sub_lanc and sub_pag == sub_lanc:
            score -= 8
            motivos.append("valor diferente, mas subcategoria compatível")
        else:
            score -= 25
            motivos.append("valor muito diferente")

    data_lanc = lancamento.get("DATA")

    if data_vencimento and data_lanc:
        diferenca_dias = abs((data_lanc - data_vencimento).days)
        if diferenca_dias <= 3:
            score += 18
            motivos.append("data próxima")
        elif diferenca_dias <= 7:
            score += 10
            motivos.append("data aceitável")
        elif data_lanc.month == data_vencimento.month and data_lanc.year == data_vencimento.year:
            score += 5
            motivos.append("mesmo mês")

    if desc_pag and desc_lanc:
        palavras_pag = {p for p in desc_pag.split() if len(p) >= 4}
        palavras_lanc = {p for p in desc_lanc.split() if len(p) >= 4}
        comuns = palavras_pag.intersection(palavras_lanc)

        if comuns:
            score += min(10, len(comuns) * 3)
            motivos.append("descrição parecida")

    return score, motivos


def conciliar_pagamentos_com_lancamentos(
    filtros: Optional[Dict[str, Any]] = None,
    id_planilha: Optional[str] = None,
    aplicar_alteracoes: bool = True,
) -> Dict[str, Any]:
    filtros = filtros or {}

    planilha, aba = garantir_estrutura_pagamentos(id_planilha)
    valores = aba.get_all_values()

    if not valores:
        return {
            "atualizados": 0,
            "possiveis": 0,
            "parciais": 0,
            "mensagem": "Sem pagamentos.",
        }

    cabecalho = valores[0]
    pagamentos = [
        preparar_pagamento_para_tela(linha_para_dict(cabecalho, linha))
        for linha in valores[1:]
        if linha and any(str(c).strip() for c in linha)
    ]

    pagamentos_filtrados = [
        item
        for item in pagamentos
        if pagamento_passa_filtros(item, filtros)
        and normalizar_texto(item.get("STATUS_CALCULADO") or item.get("STATUS")) not in {"CANCELADO"}
    ]

    lancamentos = listar_lancamentos_normalizados(id_planilha)

    atualizados = 0
    possiveis = 0
    parciais = 0
    resultados = []

    try:
        idx_status = cabecalho.index("STATUS")
        idx_valor_pago = cabecalho.index("VALOR_PAGO")
        idx_data_pagamento = cabecalho.index("DATA_PAGAMENTO")
        idx_lancamento_id = cabecalho.index("LANCAMENTO_ID")
        idx_lancamento_data = cabecalho.index("LANCAMENTO_DATA")
        idx_lancamento_desc = cabecalho.index("LANCAMENTO_DESCRICAO")
        idx_lancamento_valor = cabecalho.index("LANCAMENTO_VALOR")
        idx_match_status = cabecalho.index("MATCH_STATUS")
        idx_match_score = cabecalho.index("MATCH_SCORE")
        idx_atualizado = cabecalho.index("ATUALIZADO_EM")
    except ValueError as exc:
        raise RuntimeError(f"Cabeçalho da aba PAGAMENTOS incompleto: {exc}")

    usados_lancamentos = set()

    for pagamento in pagamentos_filtrados:
        status_atual = normalizar_texto(pagamento.get("STATUS") or pagamento.get("STATUS_CALCULADO"))

        if aplicar_alteracoes:
            pagamento_id_atual = str(pagamento.get("ID") or "")

            for idx, linha in enumerate(valores[1:], start=2):
                if linha and str(linha[0]).strip() == pagamento_id_atual:
                    while len(linha) < len(cabecalho):
                        linha.append("")

                    linha[idx_lancamento_id] = ""
                    linha[idx_lancamento_data] = ""
                    linha[idx_lancamento_desc] = ""
                    linha[idx_lancamento_valor] = ""

                    if normalizar_texto(linha[idx_status]) == "PAGO":
                        linha[idx_match_status] = "PAGAMENTO ENCONTRADO"
                        linha[idx_match_score] = linha[idx_match_score] or "MANUAL"
                    else:
                        linha[idx_match_status] = ""
                        linha[idx_match_score] = ""
                        linha[idx_valor_pago] = ""
                        linha[idx_data_pagamento] = ""

                    linha[idx_atualizado] = agora_iso()
                    valores[idx - 1] = linha
                    aba.update(f"A{idx}", [linha], value_input_option="USER_ENTERED")
                    break

        resultado_soma = None

        if pagamento_deve_conciliar_por_soma(pagamento):
            resultado_soma = conciliar_pagamento_por_soma(
                pagamento=pagamento,
                lancamentos=lancamentos,
                usados_lancamentos=usados_lancamentos,
            )

        if resultado_soma:
            novo_status = resultado_soma["novo_status"]
            match_status = resultado_soma["match_status"]
            valor_pago = resultado_soma["valor_pago"]

            if resultado_soma["tipo_resultado"] == "atualizado":
                atualizados += 1
            elif resultado_soma["tipo_resultado"] == "parcial":
                parciais += 1

            for lanc in resultado_soma.get("lancamentos", []):
                usados_lancamentos.add(lanc.get("ID"))

            resultados.append(
                {
                    "pagamento_id": pagamento.get("ID"),
                    "descricao": pagamento.get("DESCRICAO"),
                    "status": novo_status,
                    "score": resultado_soma.get("match_score"),
                    "motivos": resultado_soma.get("motivos", []),
                    "lancamento": {
                        "ID": resultado_soma.get("lancamento_id"),
                        "DATA": resultado_soma.get("data_pagamento"),
                        "DESCRICAO": resultado_soma.get("lancamento_descricao"),
                        "VALOR": valor_pago,
                    },
                }
            )

            if aplicar_alteracoes:
                pagamento_id = str(pagamento.get("ID") or "")
                linha_idx = None

                for idx, linha in enumerate(valores[1:], start=2):
                    if linha and str(linha[0]).strip() == pagamento_id:
                        linha_idx = idx
                        while len(linha) < len(cabecalho):
                            linha.append("")
                        break

                if linha_idx:
                    linha = valores[linha_idx - 1]
                    linha[idx_status] = novo_status
                    linha[idx_valor_pago] = formatar_moeda(valor_pago)
                    linha[idx_data_pagamento] = formatar_data(resultado_soma.get("data_pagamento"))
                    linha[idx_lancamento_id] = resultado_soma.get("lancamento_id") or ""
                    linha[idx_lancamento_data] = resultado_soma.get("lancamento_data") or ""
                    linha[idx_lancamento_desc] = resultado_soma.get("lancamento_descricao") or ""
                    linha[idx_lancamento_valor] = formatar_moeda(valor_pago)
                    linha[idx_match_status] = match_status
                    linha[idx_match_score] = resultado_soma.get("match_score") or ""
                    linha[idx_atualizado] = agora_iso()

                    valores[linha_idx - 1] = linha
                    aba.update(f"A{linha_idx}", [linha], value_input_option="USER_ENTERED")

            continue

        melhor = None
        melhor_score = -1
        melhores_motivos: List[str] = []

        for lanc in lancamentos:
            if lanc["ID"] in usados_lancamentos:
                continue

            if not lancamento_tem_mes_compatível_para_match_individual(pagamento, lanc):
                continue

            score, motivos = calcular_score_match(pagamento, lanc)

            if score > melhor_score:
                melhor = lanc
                melhor_score = score
                melhores_motivos = motivos

        if not melhor:
            continue

        valor_previsto = parse_moeda(pagamento.get("VALOR_PREVISTO"))
        valor_lanc = parse_moeda(melhor.get("VALOR"))

        diferenca_valor = abs(valor_previsto - valor_lanc)
        percentual_diferenca = 100.0

        if valor_previsto > 0:
            percentual_diferenca = diferenca_valor / valor_previsto * 100

        valor_igual_ou_proximo = diferenca_valor <= 1
        valor_aceitavel = percentual_diferenca <= 5
        valor_parcial_possivel = valor_lanc < valor_previsto and percentual_diferenca <= 40
        despesa_variavel = pagamento_variavel_para_match(pagamento)

        cat_pag = normalizar_categoria_match(pagamento.get("CATEGORIA"))
        sub_pag = normalizar_subcategoria_match(
            pagamento.get("CATEGORIA"),
            pagamento.get("SUBCATEGORIA"),
            pagamento.get("DESCRICAO"),
        )
        cat_lanc = normalizar_categoria_match(melhor.get("CATEGORIA_MATCH") or melhor.get("CATEGORIA"))
        sub_lanc = normalizar_texto(melhor.get("SUBCATEGORIA_MATCH") or melhor.get("SUBCATEGORIA"))
        chave_compativel = bool(cat_pag and cat_lanc and cat_pag == cat_lanc and sub_pag and sub_lanc and sub_pag == sub_lanc)

        if melhor_score >= 85 and valor_igual_ou_proximo:
            novo_status = "PAGO"
            match_status = "PAGAMENTO ENCONTRADO"
            atualizados += 1
        elif despesa_variavel and melhor_score >= 55 and chave_compativel:
            novo_status = "PAGO" if status_atual == "PAGO" else "PENDENTE"
            match_status = "PAGAMENTO ENCONTRADO" if status_atual == "PAGO" else "POSSÍVEL LANÇAMENTO"
            possiveis += 1
        elif melhor_score >= 80 and valor_parcial_possivel:
            novo_status = "PAGO" if status_atual == "PAGO" else "PARCIAL"
            match_status = "PAGAMENTO ENCONTRADO" if status_atual == "PAGO" else "PAGAMENTO PARCIAL"
            parciais += 1
        elif melhor_score >= 60 and (valor_aceitavel or chave_compativel):
            novo_status = "PAGO" if status_atual == "PAGO" else "PENDENTE"
            match_status = "PAGAMENTO ENCONTRADO" if status_atual == "PAGO" else "POSSÍVEL LANÇAMENTO"
            possiveis += 1
        elif melhor_score >= 55 and chave_compativel:
            novo_status = "PAGO" if status_atual == "PAGO" else "PENDENTE"
            match_status = "PAGAMENTO ENCONTRADO" if status_atual == "PAGO" else "POSSÍVEL LANÇAMENTO"
            possiveis += 1
        else:
            continue

        usados_lancamentos.add(melhor["ID"])

        resultados.append(
            {
                "pagamento_id": pagamento.get("ID"),
                "descricao": pagamento.get("DESCRICAO"),
                "status": novo_status,
                "score": melhor_score,
                "motivos": melhores_motivos,
                "lancamento": melhor,
            }
        )

        if aplicar_alteracoes:
            pagamento_id = str(pagamento.get("ID") or "")
            linha_idx = None

            for idx, linha in enumerate(valores[1:], start=2):
                if linha and str(linha[0]).strip() == pagamento_id:
                    linha_idx = idx
                    while len(linha) < len(cabecalho):
                        linha.append("")
                    break

            if linha_idx:
                linha = valores[linha_idx - 1]
                linha[idx_status] = novo_status
                linha[idx_valor_pago] = formatar_moeda(valor_lanc)
                linha[idx_data_pagamento] = formatar_data(melhor.get("DATA"))
                linha[idx_lancamento_id] = melhor.get("ID") or ""
                linha[idx_lancamento_data] = formatar_data(melhor.get("DATA"))
                linha[idx_lancamento_desc] = melhor.get("DESCRICAO") or ""
                linha[idx_lancamento_valor] = formatar_moeda(valor_lanc)
                linha[idx_match_status] = match_status
                linha[idx_match_score] = str(melhor_score)
                linha[idx_atualizado] = agora_iso()

                valores[linha_idx - 1] = linha
                aba.update(f"A{linha_idx}", [linha], value_input_option="USER_ENTERED")

    return {
        "atualizados": atualizados,
        "possiveis": possiveis,
        "parciais": parciais,
        "resultados": resultados,
        "mensagem": (
            f"Conferência concluída: {atualizados} pagamento(s) encontrado(s), "
            f"{possiveis} possível(is), {parciais} parcial(is)."
        ),
    }

def montar_resumo_pagamentos(pagamentos: List[Dict[str, Any]]) -> Dict[str, Any]:
    resumo = {
        "total_previsto": 0.0,
        "total_pago": 0.0,
        "total_pendente": 0.0,
        "qtd_pendentes": 0,
        "qtd_pagos": 0,
        "qtd_atrasados": 0,
        "qtd_vence_hoje": 0,
        "por_grupo": {
            "INÍCIO DO MÊS": 0.0,
            "FINAL DO MÊS": 0.0,
            "SEM DATA": 0.0,
        },
    }

    for item in pagamentos:
        previsto = parse_moeda(item.get("VALOR_PREVISTO_NUM") or item.get("VALOR_PREVISTO"))
        pago = parse_moeda(item.get("VALOR_PAGO_NUM") or item.get("VALOR_PAGO"))
        status = normalizar_texto(item.get("STATUS_CALCULADO") or item.get("STATUS"))
        grupo = item.get("GRUPO_VENCIMENTO") or "SEM DATA"

        resumo["total_previsto"] += previsto
        resumo["total_pago"] += pago

        if status == "PAGO":
            resumo["qtd_pagos"] += 1
        elif status == "ATRASADO":
            resumo["qtd_atrasados"] += 1
            resumo["qtd_pendentes"] += 1
            resumo["total_pendente"] += max(previsto - pago, 0)
        elif status == "VENCE HOJE":
            resumo["qtd_vence_hoje"] += 1
            resumo["qtd_pendentes"] += 1
            resumo["total_pendente"] += max(previsto - pago, 0)
        elif status not in {"CANCELADO"}:
            resumo["qtd_pendentes"] += 1
            resumo["total_pendente"] += max(previsto - pago, 0)

        if grupo not in resumo["por_grupo"]:
            resumo["por_grupo"][grupo] = 0.0

        resumo["por_grupo"][grupo] += previsto

    resumo["total_previsto_fmt"] = formatar_moeda(resumo["total_previsto"])
    resumo["total_pago_fmt"] = formatar_moeda(resumo["total_pago"])
    resumo["total_pendente_fmt"] = formatar_moeda(resumo["total_pendente"])
    resumo["inicio_mes_fmt"] = formatar_moeda(resumo["por_grupo"].get("INÍCIO DO MÊS", 0))
    resumo["final_mes_fmt"] = formatar_moeda(resumo["por_grupo"].get("FINAL DO MÊS", 0))

    return resumo


def adicionar_meses_data(data_base: Optional[date], meses: int = 1) -> Optional[date]:
    """
    Soma meses mantendo o dia quando possível.
    Ex.: 31/01 + 1 mês vira 28/02 ou 29/02 em ano bissexto.
    """

    if not data_base:
        return None

    mes_total = data_base.month + meses
    ano = data_base.year + ((mes_total - 1) // 12)
    mes = ((mes_total - 1) % 12) + 1

    ultimo_dia = 31

    for dia in range(31, 27, -1):
        try:
            date(ano, mes, dia)
            ultimo_dia = dia
            break
        except ValueError:
            continue

    dia_final = min(data_base.day, ultimo_dia)

    return date(ano, mes, dia_final)


def proximo_mes_ano(ano: Any, mes: Any, data_vencimento: Optional[date] = None) -> tuple[str, str]:
    """
    Calcula o próximo mês a partir do mês/ano do pagamento.
    Se não conseguir usar MES/ANO, usa a data de vencimento.
    """

    mes_num = mes_para_numero(mes)

    try:
        ano_num = int(str(ano or "").strip())
    except Exception:
        ano_num = data_vencimento.year if data_vencimento else date.today().year

    if not mes_num:
        mes_num = data_vencimento.month if data_vencimento else date.today().month

    mes_num += 1

    if mes_num > 12:
        mes_num = 1
        ano_num += 1

    return str(ano_num), mes_numero_para_sigla(mes_num)


def obter_pagamento_por_id(
    pagamento_id: str,
    id_planilha: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Busca um pagamento diretamente na aba PAGAMENTOS pelo ID.
    """

    _, aba = garantir_estrutura_pagamentos(id_planilha)
    dados = ler_aba_como_dicts(aba)

    for item in dados:
        if str(item.get("ID", "")).strip() == str(pagamento_id).strip():
            return preparar_pagamento_para_tela(item)

    raise ValueError("Pagamento não encontrado para duplicação.")


def duplicar_pagamento(
    pagamento_id: str,
    id_planilha: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Duplica um pagamento para o mês seguinte.

    Regras:
    - mantém descrição, tipo, categoria, subcategoria, valor previsto,
      recorrência, conta e observação;
    - muda ANO/MES para o mês seguinte;
    - ajusta DATA_VENCIMENTO para o mês seguinte, mantendo o dia;
    - limpa valor pago, data de pagamento e dados de conciliação;
    - novo pagamento nasce como PENDENTE.
    """

    original = obter_pagamento_por_id(pagamento_id, id_planilha=id_planilha)

    data_vencimento_original = parse_data(original.get("DATA_VENCIMENTO"))
    nova_data_vencimento = adicionar_meses_data(data_vencimento_original, 1)

    novo_ano, novo_mes = proximo_mes_ano(
        ano=original.get("ANO"),
        mes=original.get("MES"),
        data_vencimento=data_vencimento_original,
    )

    dados_novos = {
        "ano": novo_ano,
        "mes": novo_mes,
        "descricao": original.get("DESCRICAO", ""),
        "tipo": original.get("TIPO", ""),
        "categoria": original.get("CATEGORIA", ""),
        "subcategoria": original.get("SUBCATEGORIA", ""),
        "valor_previsto": original.get("VALOR_PREVISTO", ""),
        "valor_pago": "0",
        "data_vencimento": formatar_data(nova_data_vencimento),
        "data_pagamento": "",
        "status": "PENDENTE",
        "recorrente": original.get("RECORRENTE", "NÃO"),
        "conta_pagamento": original.get("CONTA_PAGAMENTO", ""),
        "observacao": original.get("OBSERVACAO", ""),
    }

    return salvar_pagamento(dados_novos, id_planilha=id_planilha)




def pagamento_duplicado_ja_existe(
    pagamentos_destino: List[Dict[str, Any]],
    dados_novos: Dict[str, Any],
) -> bool:
    """
    Evita duplicar novamente o mesmo pagamento no mês de destino.
    A comparação usa os campos principais do planejamento.
    """

    ano_novo = normalizar_texto(dados_novos.get("ano"))
    mes_novo = normalizar_texto(dados_novos.get("mes"))
    descricao_nova = normalizar_texto(dados_novos.get("descricao"))
    tipo_novo = normalizar_texto(dados_novos.get("tipo"))
    categoria_nova = normalizar_texto(dados_novos.get("categoria"))
    subcategoria_nova = normalizar_texto(dados_novos.get("subcategoria"))
    valor_novo = parse_moeda(dados_novos.get("valor_previsto"))

    for item in pagamentos_destino:
        if normalizar_texto(item.get("STATUS")) == "CANCELADO":
            continue

        mesmo_item = (
            normalizar_texto(item.get("ANO")) == ano_novo
            and normalizar_texto(item.get("MES")) == mes_novo
            and normalizar_texto(item.get("DESCRICAO")) == descricao_nova
            and normalizar_texto(item.get("TIPO")) == tipo_novo
            and normalizar_texto(item.get("CATEGORIA")) == categoria_nova
            and normalizar_texto(item.get("SUBCATEGORIA")) == subcategoria_nova
            and abs(parse_moeda(item.get("VALOR_PREVISTO")) - valor_novo) <= 0.01
        )

        if mesmo_item:
            return True

    return False


def duplicar_pagamentos_mes(
    ano_origem: str,
    mes_origem: str,
    id_planilha: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Duplica todos os pagamentos ativos de um mês para o mês seguinte.

    Versão otimizada para evitar erro 429 do Google Sheets.

    Antes, a duplicação chamava salvar_pagamento() dentro do loop. Isso fazia
    várias leituras da planilha e da aba de categorias, podendo estourar a cota
    de leitura do Google Sheets. Agora a função:
    - lê a aba PAGAMENTOS uma única vez;
    - monta todas as novas linhas em memória;
    - grava tudo de uma vez com append_rows();
    - não relê categorias para cada pagamento, porque os pagamentos de origem
      já estão validados/cadastrados.
    """

    ano_origem = str(ano_origem or "").strip()
    mes_origem = normalizar_texto(mes_origem)

    if not ano_origem:
        raise ValueError("Informe o ano de origem para duplicar os pagamentos.")

    if not mes_origem:
        raise ValueError("Informe o mês de origem para duplicar os pagamentos.")

    mes_num_origem = mes_para_numero(mes_origem)
    if not mes_num_origem:
        raise ValueError("Mês de origem inválido.")

    # Uma única abertura/leitura da aba de pagamentos.
    _, aba = garantir_estrutura_pagamentos(id_planilha)
    valores = aba.get_all_values()

    if not valores:
        return {
            "ok": True,
            "criados": 0,
            "ignorados": 0,
            "ano_destino": ano_origem,
            "mes_destino": mes_origem,
            "pagamentos_criados": [],
            "mensagem": "A aba de pagamentos está vazia.",
        }

    cabecalho = valores[0]
    dados = [
        linha_para_dict(cabecalho, linha)
        for linha in valores[1:]
        if linha and any(str(c).strip() for c in linha)
    ]

    pagamentos_origem = []

    for item in dados:
        item_preparado = preparar_pagamento_para_tela(item)

        if normalizar_texto(item_preparado.get("STATUS")) == "CANCELADO":
            continue

        if str(item_preparado.get("ANO", "")).strip() != ano_origem:
            continue

        if normalizar_texto(item_preparado.get("MES")) != mes_origem:
            continue

        pagamentos_origem.append(item_preparado)

    if not pagamentos_origem:
        return {
            "ok": True,
            "criados": 0,
            "ignorados": 0,
            "ano_destino": ano_origem,
            "mes_destino": mes_origem,
            "pagamentos_criados": [],
            "mensagem": "Nenhum pagamento ativo encontrado para duplicar.",
        }

    primeiro = pagamentos_origem[0]
    data_ref = parse_data(primeiro.get("DATA_VENCIMENTO"))
    ano_destino, mes_destino = proximo_mes_ano(
        ano=ano_origem,
        mes=mes_origem,
        data_vencimento=data_ref,
    )

    pagamentos_destino = [
        preparar_pagamento_para_tela(item)
        for item in dados
        if str(item.get("ANO", "")).strip() == ano_destino
        and normalizar_texto(item.get("MES")) == normalizar_texto(mes_destino)
    ]

    linhas_novas = []
    pagamentos_criados = []
    ignorados = 0
    estrutura_categorias = obter_opcoes_categorias(id_planilha)

    for original in pagamentos_origem:
        data_vencimento_original = parse_data(original.get("DATA_VENCIMENTO"))
        nova_data_vencimento = adicionar_meses_data(data_vencimento_original, 1)

        dados_novos = {
            "ano": ano_destino,
            "mes": mes_destino,
            "descricao": original.get("DESCRICAO", ""),
            "tipo": original.get("TIPO", ""),
            "categoria": original.get("CATEGORIA", ""),
            "subcategoria": original.get("SUBCATEGORIA", ""),
            "valor_previsto": original.get("VALOR_PREVISTO", ""),
            "valor_pago": "0",
            "data_vencimento": formatar_data(nova_data_vencimento),
            "data_pagamento": "",
            "status": "PENDENTE",
            "recorrente": original.get("RECORRENTE", "NÃO"),
            "conta_pagamento": original.get("CONTA_PAGAMENTO", ""),
            "observacao": original.get("OBSERVACAO", ""),
        }

        if pagamento_duplicado_ja_existe(pagamentos_destino, dados_novos):
            ignorados += 1
            continue

        try:
            tipo_oficial, categoria_oficial, subcategoria_oficial = resolver_categoria_na_estrutura(
                dados_novos.get("tipo"),
                dados_novos.get("categoria"),
                dados_novos.get("subcategoria"),
                estrutura_categorias,
            )
        except Exception:
            # Pagamentos antigos fora da aba CATEGORIAS não são duplicados.
            # Assim a duplicação mensal não propaga classificações antigas.
            ignorados += 1
            continue

        pagamento_id = str(uuid.uuid4())
        criado_em = agora_iso()

        registro = {
            "ID": pagamento_id,
            "ANO": ano_destino,
            "MES": mes_destino,
            "DESCRICAO": str(dados_novos.get("descricao") or "").strip(),
            "TIPO": tipo_oficial,
            "CATEGORIA": categoria_oficial,
            "SUBCATEGORIA": subcategoria_oficial,
            "VALOR_PREVISTO": formatar_moeda(dados_novos.get("valor_previsto") or 0),
            "VALOR_PAGO": formatar_moeda(0),
            "DATA_VENCIMENTO": dados_novos.get("data_vencimento") or "",
            "DATA_PAGAMENTO": "",
            "STATUS": "PENDENTE",
            "RECORRENTE": normalizar_texto(dados_novos.get("recorrente") or "NÃO"),
            "CONTA_PAGAMENTO": str(dados_novos.get("conta_pagamento") or "").strip(),
            "OBSERVACAO": str(dados_novos.get("observacao") or "").strip(),
            "LANCAMENTO_ID": "",
            "LANCAMENTO_DATA": "",
            "LANCAMENTO_DESCRICAO": "",
            "LANCAMENTO_VALOR": "",
            "MATCH_STATUS": "",
            "MATCH_SCORE": "",
            "CRIADO_EM": criado_em,
            "ATUALIZADO_EM": criado_em,
        }

        linha_final = [registro.get(coluna, "") for coluna in CABECALHO_PAGAMENTOS]
        linhas_novas.append(linha_final)

        novo_preparado = preparar_pagamento_para_tela(registro)
        pagamentos_destino.append(novo_preparado)
        pagamentos_criados.append(novo_preparado)

    if linhas_novas:
        # Uma única escrita para todas as linhas novas.
        aba.append_rows(linhas_novas, value_input_option="USER_ENTERED")

    criados = len(linhas_novas)

    mensagem = (
        f"Pagamentos duplicados de {mes_origem}/{ano_origem} para "
        f"{mes_destino}/{ano_destino}. Criados: {criados}. Ignorados: {ignorados}."
    )

    return {
        "ok": True,
        "criados": criados,
        "ignorados": ignorados,
        "ano_destino": ano_destino,
        "mes_destino": mes_destino,
        "pagamentos_criados": pagamentos_criados,
        "mensagem": mensagem,
    }


def excluir_pagamento(pagamento_id: str, id_planilha: Optional[str] = None) -> bool:
    _, aba = garantir_estrutura_pagamentos(id_planilha)
    valores = aba.get_all_values()

    for idx, linha in enumerate(valores[1:], start=2):
        if linha and str(linha[0]).strip() == str(pagamento_id):
            aba.delete_rows(idx)
            return True

    return False