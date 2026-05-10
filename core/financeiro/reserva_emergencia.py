from __future__ import annotations

from datetime import datetime
from typing import Any


ABA_BASE_LANCAMENTOS = "BASE_LANCAMENTOS"

MESES_ORDEM = [
    ("JAN", 1),
    ("FEV", 2),
    ("MAR", 3),
    ("ABR", 4),
    ("MAI", 5),
    ("JUN", 6),
    ("JUL", 7),
    ("AGO", 8),
    ("SET", 9),
    ("OUT", 10),
    ("NOV", 11),
    ("DEZ", 12),
]

MESES_NUMERO_POR_SIGLA = {sigla: numero for sigla, numero in MESES_ORDEM}

LIQUIDEZ_RESERVA_ATIVOS = {
    "CC BB",
    "CC CAIXA",
    "NUBANK",
    "PAGBANK",
    "PICPAY",
    "POUP BB",
    "POUP CAIXA",
    "COFRE",
    "EM MAOS",
    "EM MÃOS",
}


def obter_planilha_configurada():
    """
    Obtém a planilha vinculada na configuração do sistema.

    Tenta primeiro o caminho usado pelo orçamento, depois configuração
    e por fim patrimônio, mantendo compatibilidade com o projeto.
    """

    tentativas = []

    try:
        from core.financeiro.orcamento_google import obter_planilha

        return obter_planilha()
    except Exception as erro:
        tentativas.append(f"core.financeiro.orcamento_google.obter_planilha: {erro}")

    try:
        from core.financeiro.configuracoes_google import obter_planilha

        return obter_planilha()
    except Exception as erro:
        tentativas.append(f"core.financeiro.configuracoes_google.obter_planilha: {erro}")

    try:
        from core.financeiro.patrimonio_google import obter_planilha

        return obter_planilha()
    except Exception as erro:
        tentativas.append(f"core.financeiro.patrimonio_google.obter_planilha: {erro}")

    detalhes = " | ".join(tentativas)

    raise RuntimeError(
        "Não foi possível obter a planilha configurada. "
        "A função obter_planilha não foi localizada nos módulos esperados. "
        f"Detalhes: {detalhes}"
    )


def normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""

    texto = str(valor).strip().upper()

    trocas = {
        "Á": "A",
        "À": "A",
        "Ã": "A",
        "Â": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)

    return texto


def formatar_moeda(valor: Any) -> str:
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0

    texto = f"R$ {numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor: float) -> str:
    return f"{valor:.1f}%".replace(".", ",")


def converter_valor(valor: Any) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .strip()
    )

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def localizar_valor_linha(linha: dict, nomes_possiveis: list[str]) -> Any:
    mapa = {normalizar_texto(chave): valor for chave, valor in linha.items()}

    for nome in nomes_possiveis:
        chave = normalizar_texto(nome)

        if chave in mapa:
            return mapa[chave]

    return ""


def obter_mes_numero_da_linha(linha: dict) -> int | None:
    valor_mes = localizar_valor_linha(
        linha,
        [
            "MES",
            "MÊS",
            "MES_REFERENCIA",
            "MÊS_REFERENCIA",
            "REFERENCIA",
            "MÊS REF",
            "MES REF",
        ],
    )

    if valor_mes:
        texto_mes = normalizar_texto(valor_mes)

        if texto_mes in MESES_NUMERO_POR_SIGLA:
            return MESES_NUMERO_POR_SIGLA[texto_mes]

        try:
            numero = int(float(texto_mes))
            if 1 <= numero <= 12:
                return numero
        except Exception:
            pass

    valor_data = localizar_valor_linha(
        linha,
        [
            "DATA",
            "DATA_MOVIMENTO",
            "DATA MOVIMENTO",
            "DATA DO LANÇAMENTO",
            "DATA LANCAMENTO",
            "DATA_LANCAMENTO",
        ],
    )

    if not valor_data:
        return None

    texto_data = str(valor_data).strip()

    formatos = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto_data[:10], formato).month
        except Exception:
            continue

    return None


def obter_ano_da_linha(linha: dict) -> int | None:
    valor_ano = localizar_valor_linha(
        linha,
        [
            "ANO",
            "ANO_REFERENCIA",
            "ANO REF",
        ],
    )

    if valor_ano:
        try:
            return int(float(str(valor_ano).strip()))
        except Exception:
            pass

    valor_data = localizar_valor_linha(
        linha,
        [
            "DATA",
            "DATA_MOVIMENTO",
            "DATA MOVIMENTO",
            "DATA DO LANÇAMENTO",
            "DATA LANCAMENTO",
            "DATA_LANCAMENTO",
        ],
    )

    if not valor_data:
        return None

    texto_data = str(valor_data).strip()

    formatos = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto_data[:10], formato).year
        except Exception:
            continue

    return None


def obter_valor_realizado_da_linha(linha: dict) -> float:
    """
    Lê o valor efetivamente realizado da BASE_LANCAMENTOS.

    Na base atual, VALOR_REALIZADO pode vir em centavos:
    17999 = R$ 179,99
    14792 = R$ 147,92

    Por isso, quando o valor vier como número inteiro puro e alto,
    convertemos para reais dividindo por 100.
    """

    valor_bruto = localizar_valor_linha(
        linha,
        [
            "VALOR_REALIZADO",
            "VALOR REALIZADO",
            "REALIZADO",
            "VALOR",
            "VALOR_NUMERICO",
            "VALOR NUMERICO",
            "VALOR AJUSTADO",
            "VALOR_AJUSTADO",
        ],
    )

    valor = converter_valor(valor_bruto)
    texto = str(valor_bruto).strip()

    # Caso típico da sua BASE_LANCAMENTOS:
    # 17999, 15733, 14792 etc. representam centavos.
    # Só divide quando vier inteiro puro, sem vírgula/ponto, para não mexer em valores já formatados.
    if texto.isdigit() and abs(valor) >= 1000:
        return valor / 100

    return valor


def linha_eh_despesa(linha: dict) -> bool:
    tipo = normalizar_texto(
        localizar_valor_linha(
            linha,
            [
                "TIPO",
                "TIPO_LANCAMENTO",
                "TIPO LANÇAMENTO",
                "TIPO LANCAMENTO",
                "NATUREZA",
            ],
        )
    )

    categoria = normalizar_texto(
        localizar_valor_linha(
            linha,
            [
                "CATEGORIA",
                "CATEGORIA_AJUSTADA",
                "CATEGORIA AJUSTADA",
            ],
        )
    )

    subcategoria = normalizar_texto(
        localizar_valor_linha(
            linha,
            [
                "SUBCATEGORIA",
                "SUB_CATEGORIA",
                "SUB CATEGORIA",
            ],
        )
    )

    situacao = normalizar_texto(
        localizar_valor_linha(
            linha,
            [
                "SITUACAO",
                "SITUAÇÃO",
            ],
        )
    )

    texto_completo = f"{tipo} {categoria} {subcategoria} {situacao}"

    if "TRANSFERENCIA" in texto_completo:
        return False

    if "TRANSFERÊNCIA" in texto_completo:
        return False

    if "INVESTIMENTO" in texto_completo:
        return False

    if "APLICACAO" in texto_completo:
        return False

    if "APLICAÇÃO" in texto_completo:
        return False

    if "RESGATE" in texto_completo:
        return False

    if "RECEITA" in texto_completo:
        return False

    if "DESPESA" in texto_completo:
        return True

    valor = obter_valor_realizado_da_linha(linha)

    return valor < 0


def calcular_despesas_mensais(ano: str | int, mes_limite: str | None = None) -> dict:
    ano_numero = int(ano)
    mes_limite_numero = MESES_NUMERO_POR_SIGLA.get(normalizar_texto(mes_limite), 12)

    planilha = obter_planilha_configurada()
    aba = planilha.worksheet(ABA_BASE_LANCAMENTOS)
    registros = aba.get_all_records()

    despesas_por_mes = {numero: 0.0 for _, numero in MESES_ORDEM}

    linhas_consideradas = 0

    for linha in registros:
        if not linha_eh_despesa(linha):
            continue

        ano_linha = obter_ano_da_linha(linha)
        mes_linha = obter_mes_numero_da_linha(linha)

        if ano_linha != ano_numero:
            continue

        if not mes_linha:
            continue

        if mes_linha > mes_limite_numero:
            continue

        valor = obter_valor_realizado_da_linha(linha)

        despesas_por_mes[mes_linha] += abs(valor)
        linhas_consideradas += 1

    meses_com_despesa = [
        valor for mes, valor in despesas_por_mes.items()
        if mes <= mes_limite_numero and valor > 0
    ]

    total_despesas = sum(meses_com_despesa)
    qtd_meses = len(meses_com_despesa)

    media_mensal = total_despesas / qtd_meses if qtd_meses else 0.0

    detalhamento = []

    for sigla, numero in MESES_ORDEM:
        if numero > mes_limite_numero:
            continue

        valor_mes = despesas_por_mes.get(numero, 0.0)

        detalhamento.append(
            {
                "mes": sigla,
                "numero": numero,
                "despesa": valor_mes,
                "despesa_fmt": formatar_moeda(valor_mes),
            }
        )

    return {
        "ok": qtd_meses > 0,
        "ano": ano_numero,
        "mes_limite": mes_limite,
        "mes_limite_numero": mes_limite_numero,
        "linhas_consideradas": linhas_consideradas,
        "qtd_meses": qtd_meses,
        "total_despesas": total_despesas,
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "media_mensal": media_mensal,
        "media_mensal_fmt": formatar_moeda(media_mensal),
        "detalhamento": detalhamento,
    }


def calcular_liquidez_disponivel(resumo_patrimonio: dict) -> dict:
    ativos = resumo_patrimonio.get("ativos", [])

    itens = []
    total_liquidez = 0.0

    for ativo in ativos:
        nome = normalizar_texto(ativo.get("nome", ""))

        if nome not in LIQUIDEZ_RESERVA_ATIVOS:
            continue

        valor = float(ativo.get("fim", 0) or 0)
        total_liquidez += valor

        itens.append(
            {
                "nome": ativo.get("nome", ""),
                "valor": valor,
                "valor_fmt": formatar_moeda(valor),
            }
        )

    return {
        "total": total_liquidez,
        "total_fmt": formatar_moeda(total_liquidez),
        "itens": itens,
    }


def classificar_reserva(
    liquidez_atual: float,
    reserva_6_meses: float,
    reserva_12_meses: float,
) -> dict:
    if reserva_6_meses <= 0:
        return {
            "situacao": "SEM BASE DE DESPESAS",
            "classe": "amber",
            "mensagem": (
                "Não foi possível calcular a reserva ideal porque não há despesas suficientes "
                "na base de lançamentos para o período analisado."
            ),
            "percentual_cobertura": 0.0,
            "percentual_cobertura_fmt": "0,0%",
        }

    percentual = liquidez_atual / reserva_6_meses * 100

    if liquidez_atual < reserva_6_meses:
        return {
            "situacao": "RESERVA INSUFICIENTE",
            "classe": "red",
            "mensagem": (
                "A liquidez atual está abaixo da reserva recomendada de 6 meses. "
                "Antes de aumentar risco em ações, FIIs ou cripto, o cliente deveria reforçar "
                "a reserva de emergência."
            ),
            "percentual_cobertura": percentual,
            "percentual_cobertura_fmt": formatar_percentual(percentual),
        }

    if liquidez_atual <= reserva_12_meses:
        return {
            "situacao": "RESERVA ADEQUADA",
            "classe": "green",
            "mensagem": (
                "A liquidez atual cobre pelo menos 6 meses de despesas. "
                "O cliente tem uma base adequada de segurança para avaliar objetivos de médio "
                "e longo prazo."
            ),
            "percentual_cobertura": percentual,
            "percentual_cobertura_fmt": formatar_percentual(percentual),
        }

    return {
        "situacao": "EXCESSO DE LIQUIDEZ",
        "classe": "amber",
        "mensagem": (
            "A liquidez atual ultrapassa 12 meses de despesas. "
            "Pode haver excesso de dinheiro parado em instrumentos conservadores, permitindo avaliar "
            "realocação gradual para objetivos de médio e longo prazo."
        ),
        "percentual_cobertura": percentual,
        "percentual_cobertura_fmt": formatar_percentual(percentual),
    }


def montar_reserva_emergencia(
    ano: str | int,
    mes: str,
    resumo_patrimonio: dict,
) -> dict:
    despesas = calcular_despesas_mensais(ano=ano, mes_limite=mes)
    liquidez = calcular_liquidez_disponivel(resumo_patrimonio)

    media_mensal = despesas["media_mensal"]

    reserva_3 = media_mensal * 3
    reserva_6 = media_mensal * 6
    reserva_12 = media_mensal * 12

    liquidez_atual = liquidez["total"]

    falta_para_6 = max(reserva_6 - liquidez_atual, 0)
    excesso_acima_12 = max(liquidez_atual - reserva_12, 0)

    classificacao = classificar_reserva(
        liquidez_atual=liquidez_atual,
        reserva_6_meses=reserva_6,
        reserva_12_meses=reserva_12,
    )

    if falta_para_6 > 0:
        orientacao = (
            f"Prioridade: formar reserva. Faltam aproximadamente "
            f"{formatar_moeda(falta_para_6)} para atingir 6 meses de despesas. "
            "Enquanto isso, o ideal é manter foco em liquidez diária, segurança e baixo risco."
        )
    elif excesso_acima_12 > 0:
        orientacao = (
            f"O cliente possui aproximadamente {formatar_moeda(excesso_acima_12)} acima de "
            "12 meses de despesas em liquidez. Esse excedente pode ser analisado para objetivos "
            "de médio e longo prazo, respeitando perfil de risco."
        )
    else:
        orientacao = (
            "A reserva está em faixa adequada. O próximo passo é separar objetivos: curto prazo, "
            "médio prazo e longo prazo, evitando usar a reserva em ativos de risco."
        )

    return {
        "ok": despesas["ok"],
        "ano": str(ano),
        "mes": mes,

        "despesas": despesas,
        "liquidez": liquidez,

        "media_mensal": media_mensal,
        "media_mensal_fmt": formatar_moeda(media_mensal),

        "reserva_3_meses": reserva_3,
        "reserva_3_meses_fmt": formatar_moeda(reserva_3),

        "reserva_6_meses": reserva_6,
        "reserva_6_meses_fmt": formatar_moeda(reserva_6),

        "reserva_12_meses": reserva_12,
        "reserva_12_meses_fmt": formatar_moeda(reserva_12),

        "liquidez_atual": liquidez_atual,
        "liquidez_atual_fmt": formatar_moeda(liquidez_atual),

        "falta_para_6_meses": falta_para_6,
        "falta_para_6_meses_fmt": formatar_moeda(falta_para_6),

        "excesso_acima_12_meses": excesso_acima_12,
        "excesso_acima_12_meses_fmt": formatar_moeda(excesso_acima_12),

        "classificacao": classificacao,
        "orientacao": orientacao,
    }