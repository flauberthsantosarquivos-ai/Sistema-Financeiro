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
    try:
        estrutura = obter_estrutura_categorias(incluir_inativas=False)
        return estrutura or deepcopy(CATEGORIAS_PADRAO)
    except Exception:
        return deepcopy(CATEGORIAS_PADRAO)


def validar_categoria_subcategoria(
    tipo: str,
    categoria: str,
    subcategoria: str,
    id_planilha: Optional[str] = None,
) -> Tuple[str, str, str]:
    try:
        return validar_categoria_subcategoria_oficial(tipo, categoria, subcategoria)
    except Exception:
        tipo_norm = normalizar_texto(tipo)
        categoria_norm = normalizar_texto(categoria)
        subcategoria_norm = normalizar_texto(subcategoria)

        opcoes = obter_opcoes_categorias(id_planilha)

        if tipo_norm not in opcoes:
            raise ValueError(f"Tipo não cadastrado na base de categorias: {tipo}")

        if categoria_norm not in opcoes[tipo_norm]:
            raise ValueError(f"Categoria não cadastrada para {tipo_norm}: {categoria}")

        subcategorias = [normalizar_texto(s) for s in opcoes[tipo_norm][categoria_norm]]

        if subcategoria_norm and subcategoria_norm not in subcategorias:
            raise ValueError(
                f"Subcategoria não cadastrada para {tipo_norm}/{categoria_norm}: {subcategoria}"
            )

        return tipo_norm, categoria_norm, subcategoria_norm


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


def normalizar_lancamento(item: Dict[str, Any], indice: int) -> Dict[str, Any]:
    data_raw = obter_campo(item, ["DATA", "DATA_LANCAMENTO", "DATA LANÇAMENTO", "DATA DO LANÇAMENTO"])
    descricao = obter_campo(item, ["DESCRICAO", "DESCRIÇÃO", "HISTORICO", "HISTÓRICO"])
    tipo = obter_campo(item, ["TIPO"])
    categoria = obter_campo(item, ["CATEGORIA"])
    subcategoria = obter_campo(item, ["SUBCATEGORIA", "SUB CATEGORIA"])
    valor = obter_campo(item, ["VALOR", "VALOR_NUM", "VALOR REALIZADO", "VALOR_REALIZADO"])
    conta = obter_campo(item, ["CONTA", "CONTA_PAGAMENTO", "BANCO"])

    lancamento_id = obter_campo(item, ["ID", "LANCAMENTO_ID", "ID_LANCAMENTO"]) or f"LINHA-{indice}"

    return {
        "ID": str(lancamento_id),
        "DATA": parse_data(data_raw),
        "DATA_RAW": str(data_raw or ""),
        "DESCRICAO": str(descricao or ""),
        "TIPO": normalizar_texto(tipo),
        "CATEGORIA": normalizar_texto(categoria),
        "SUBCATEGORIA": normalizar_texto(subcategoria),
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

    cat_pag = normalizar_texto(pagamento.get("CATEGORIA"))
    sub_pag = normalizar_texto(pagamento.get("SUBCATEGORIA"))
    desc_pag = normalizar_texto(pagamento.get("DESCRICAO"))

    valor_previsto = parse_moeda(pagamento.get("VALOR_PREVISTO"))
    data_vencimento = parse_data(pagamento.get("DATA_VENCIMENTO"))

    if cat_pag and cat_pag == normalizar_texto(lancamento.get("CATEGORIA")):
        score += 35
        motivos.append("categoria igual")

    if sub_pag and sub_pag == normalizar_texto(lancamento.get("SUBCATEGORIA")):
        score += 35
        motivos.append("subcategoria igual")

    valor_lanc = parse_moeda(lancamento.get("VALOR"))
    diferenca_valor = abs(valor_previsto - valor_lanc)

    if valor_previsto > 0:
        percentual_diferenca = diferenca_valor / valor_previsto * 100

        if diferenca_valor <= 1:
            score += 35
            motivos.append("valor igual/próximo")
        elif percentual_diferenca <= 5:
            score += 15
            motivos.append("valor próximo")
        elif valor_lanc < valor_previsto and valor_lanc > 0:
            proporcao = valor_lanc / valor_previsto
            if proporcao >= 0.5 and percentual_diferenca <= 25:
                score += 6
                motivos.append("possível pagamento parcial")
            else:
                score -= 45
                motivos.append("valor muito diferente")
        else:
            score -= 45
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

    desc_lanc = normalizar_texto(lancamento.get("DESCRICAO"))

    if desc_pag and desc_lanc:
        palavras_pag = {p for p in desc_pag.split() if len(p) >= 4}
        palavras_lanc = {p for p in desc_lanc.split() if len(p) >= 4}
        comuns = palavras_pag.intersection(palavras_lanc)

        if comuns:
            score += min(5, len(comuns) * 2)
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

        melhor = None
        melhor_score = -1
        melhores_motivos: List[str] = []

        for lanc in lancamentos:
            if lanc["ID"] in usados_lancamentos:
                continue

            data_lanc = lanc.get("DATA")
            if data_lanc:
                ano_pag = str(pagamento.get("ANO") or "")
                mes_pag = mes_para_numero(pagamento.get("MES"))

                if ano_pag and str(data_lanc.year) != ano_pag:
                    continue

                if mes_pag and data_lanc.month != mes_pag:
                    data_venc = parse_data(pagamento.get("DATA_VENCIMENTO"))
                    if not data_venc or abs((data_lanc - data_venc).days) > 7:
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
        valor_parcial_possivel = valor_lanc < valor_previsto and percentual_diferenca <= 25

        if melhor_score >= 85 and valor_igual_ou_proximo:
            novo_status = "PAGO"
            match_status = "PAGAMENTO ENCONTRADO"
            atualizados += 1
        elif melhor_score >= 80 and valor_parcial_possivel:
            novo_status = "PAGO" if status_atual == "PAGO" else "PARCIAL"
            match_status = "PAGAMENTO ENCONTRADO" if status_atual == "PAGO" else "PAGAMENTO PARCIAL"
            parciais += 1
        elif melhor_score >= 60 and valor_aceitavel:
            novo_status = "PAGO" if status_atual == "PAGO" else "PENDENTE"
            match_status = "PAGAMENTO ENCONTRADO" if status_atual == "PAGO" else "POSSÍVEL LANÇAMENTO"
            possiveis += 1
        elif melhor_score >= 70 and valor_parcial_possivel:
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


def excluir_pagamento(pagamento_id: str, id_planilha: Optional[str] = None) -> bool:
    _, aba = garantir_estrutura_pagamentos(id_planilha)
    valores = aba.get_all_values()

    for idx, linha in enumerate(valores[1:], start=2):
        if linha and str(linha[0]).strip() == str(pagamento_id):
            aba.delete_rows(idx)
            return True

    return False