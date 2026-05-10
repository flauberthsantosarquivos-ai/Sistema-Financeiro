from __future__ import annotations

from datetime import date
from typing import Any

import requests

from core.financeiro.dashboard_base import formatar_moeda
from core.financeiro.patrimonio_google import (
    MESES_OPCOES,
    montar_resumo_patrimonio,
    normalizar_upper,
)
from core.financeiro.radar_mercado import montar_radar_mercado


CLASSES_ATIVOS = {
    "POUP BB": "POUPANÇA",
    "POUP CAIXA": "POUPANÇA",

    "CC BB": "LIQUIDEZ IMEDIATA",
    "CC CAIXA": "LIQUIDEZ IMEDIATA",
    "NUBANK": "LIQUIDEZ IMEDIATA",
    "PAGBANK": "LIQUIDEZ IMEDIATA",
    "PICPAY": "LIQUIDEZ IMEDIATA",

    "AÇÕES NUINVEST": "RENDA VARIÁVEL",
    "CRIPTOMOEDAS": "CRIPTOATIVOS",

    "COFRE": "DINHEIRO FÍSICO",
    "EM MÃOS": "DINHEIRO FÍSICO",
}


ORDEM_CLASSES = [
    "LIQUIDEZ IMEDIATA",
    "POUPANÇA",
    "RENDA FIXA",
    "RENDA VARIÁVEL",
    "CRIPTOATIVOS",
    "DINHEIRO FÍSICO",
    "OUTROS",
]


CORES_CLASSES = {
    "LIQUIDEZ IMEDIATA": "#1d4ed8",
    "POUPANÇA": "#0891b2",
    "RENDA FIXA": "#047857",
    "RENDA VARIÁVEL": "#7c3aed",
    "CRIPTOATIVOS": "#dc2626",
    "DINHEIRO FÍSICO": "#b45309",
    "OUTROS": "#64748b",
}


def obter_mes_atual_sigla() -> str:
    indice = date.today().month - 1
    return MESES_OPCOES[indice][0]


def para_percentual(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def classe_do_ativo(nome_ativo: Any) -> str:
    ativo = normalizar_upper(nome_ativo)
    return CLASSES_ATIVOS.get(ativo, "OUTROS")


def obter_selic_anualizada_atual() -> dict:
    """
    Busca a Selic anualizada base 252 no SGS/BCB.

    Série usada:
    1178 - Selic anualizada base 252.

    Se o computador estiver sem internet ou o BCB indisponível,
    retorna fallback sem quebrar a tela.
    """
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/1?formato=json"

    try:
        resposta = requests.get(url, timeout=8)
        resposta.raise_for_status()

        dados = resposta.json()

        if not dados:
            raise ValueError("API do Banco Central retornou lista vazia.")

        ultimo = dados[-1]
        valor = float(str(ultimo.get("valor", "0")).replace(",", "."))

        return {
            "ok": True,
            "fonte": "Banco Central do Brasil - SGS 1178",
            "data": ultimo.get("data", ""),
            "selic_anual": valor,
            "selic_anual_fmt": para_percentual(valor),
            "mensagem": "Selic anualizada obtida automaticamente pelo Banco Central.",
        }

    except Exception as e:
        return {
            "ok": False,
            "fonte": "Fallback interno",
            "data": "",
            "selic_anual": 0.0,
            "selic_anual_fmt": "Não disponível",
            "mensagem": (
                "Não foi possível consultar a Selic automaticamente. "
                f"Detalhe técnico: {e}"
            ),
        }


def classificar_cenario_juros(selic_anual: float) -> dict:
    if selic_anual >= 10:
        return {
            "nivel": "JUROS ALTOS",
            "cor": "green",
            "diagnostico": (
                "O cenário de juros está elevado. Em geral, isso favorece alternativas "
                "conservadoras de renda fixa pós-fixada, especialmente para reserva "
                "de emergência e objetivos de curto prazo."
            ),
            "direcionamento": [
                "Priorizar reserva de emergência em liquidez diária.",
                "Avaliar Tesouro Selic para parte conservadora do patrimônio.",
                "Avaliar CDBs com liquidez diária e rendimento competitivo em relação ao CDI.",
                "Comparar poupança com alternativas conservadoras de renda fixa.",
            ],
        }

    if selic_anual >= 7:
        return {
            "nivel": "JUROS INTERMEDIÁRIOS",
            "cor": "amber",
            "diagnostico": (
                "O cenário de juros está em faixa intermediária. Ainda pode haver boas "
                "opções em renda fixa, mas a escolha entre liquidez diária, prefixado "
                "e IPCA+ passa a depender mais do prazo e do objetivo do dinheiro."
            ),
            "direcionamento": [
                "Separar dinheiro de curto, médio e longo prazo.",
                "Manter reserva em liquidez diária.",
                "Avaliar renda fixa de prazo definido apenas para valores sem uso imediato.",
                "Evitar concentrar todo o patrimônio em um único produto.",
            ],
        }

    if selic_anual > 0:
        return {
            "nivel": "JUROS BAIXOS",
            "cor": "red",
            "diagnostico": (
                "O cenário de juros está mais baixo. A renda fixa conservadora tende a "
                "render menos, o que aumenta a importância de planejamento, diversificação "
                "e definição de objetivos."
            ),
            "direcionamento": [
                "Manter reserva de emergência em produto seguro e líquido.",
                "Avaliar diversificação gradual para médio e longo prazo.",
                "Não assumir risco apenas para buscar rentabilidade maior.",
                "Separar claramente reserva, objetivos e crescimento patrimonial.",
            ],
        }

    return {
        "nivel": "CENÁRIO NÃO CONSULTADO",
        "cor": "amber",
        "diagnostico": (
            "Não foi possível obter automaticamente o cenário de juros. "
            "As sugestões abaixo usam apenas a composição patrimonial cadastrada."
        ),
        "direcionamento": [
            "Conferir manualmente Selic, CDI e inflação antes de tomar decisão.",
            "Usar as sugestões como diagnóstico patrimonial preliminar.",
        ],
    }


def montar_distribuicao_por_classe(ativos: list[dict]) -> list[dict]:
    agrupado: dict[str, dict] = {}

    total = sum(float(item.get("fim", 0) or 0) for item in ativos)

    for ativo in ativos:
        nome = ativo.get("nome", "")
        classe = classe_do_ativo(nome)
        valor = float(ativo.get("fim", 0) or 0)

        if classe not in agrupado:
            agrupado[classe] = {
                "classe": classe,
                "valor": 0.0,
                "ativos": [],
                "cor": CORES_CLASSES.get(classe, "#64748b"),
            }

        agrupado[classe]["valor"] += valor
        agrupado[classe]["ativos"].append(
            {
                "nome": nome,
                "valor": valor,
                "valor_fmt": formatar_moeda(valor),
            }
        )

    distribuicao = []

    for classe, dados in agrupado.items():
        percentual = 0.0

        if total > 0:
            percentual = dados["valor"] / total * 100

        dados["percentual"] = percentual
        dados["percentual_fmt"] = para_percentual(percentual)
        dados["valor_fmt"] = formatar_moeda(dados["valor"])

        distribuicao.append(dados)

    return sorted(
        distribuicao,
        key=lambda item: (
            ORDEM_CLASSES.index(item["classe"])
            if item["classe"] in ORDEM_CLASSES
            else 999
        ),
    )


def buscar_classe(distribuicao: list[dict], classe: str) -> dict:
    for item in distribuicao:
        if item.get("classe") == classe:
            return item

    return {
        "classe": classe,
        "valor": 0.0,
        "valor_fmt": formatar_moeda(0),
        "percentual": 0.0,
        "percentual_fmt": "0,0%",
        "ativos": [],
        "cor": CORES_CLASSES.get(classe, "#64748b"),
    }


def definir_perfil_aproximado(distribuicao: list[dict]) -> dict:
    poupanca = buscar_classe(distribuicao, "POUPANÇA")["percentual"]
    liquidez = buscar_classe(distribuicao, "LIQUIDEZ IMEDIATA")["percentual"]
    renda_variavel = buscar_classe(distribuicao, "RENDA VARIÁVEL")["percentual"]
    cripto = buscar_classe(distribuicao, "CRIPTOATIVOS")["percentual"]
    dinheiro_fisico = buscar_classe(distribuicao, "DINHEIRO FÍSICO")["percentual"]

    defensivo = poupanca + liquidez + dinheiro_fisico
    risco = renda_variavel + cripto

    if risco >= 35 or cripto >= 15:
        return {
            "perfil": "ARROJADO OU CONCENTRADO EM RISCO",
            "classe_cor": "red",
            "descricao": (
                "A composição mostra presença relevante de ativos de risco. "
                "É importante confirmar se isso está de acordo com o perfil do cliente "
                "e se a reserva de emergência está protegida."
            ),
        }

    if risco >= 15:
        return {
            "perfil": "MODERADO",
            "classe_cor": "amber",
            "descricao": (
                "Há alguma exposição a risco, mas ainda existe parcela relevante em ativos "
                "conservadores. O foco deve ser equilíbrio entre segurança, liquidez e crescimento."
            ),
        }

    if defensivo >= 70:
        return {
            "perfil": "CONSERVADOR",
            "classe_cor": "green",
            "descricao": (
                "O patrimônio está majoritariamente em ativos conservadores ou de liquidez. "
                "Isso reduz volatilidade, mas pode indicar perda de eficiência se houver excesso "
                "em poupança ou conta corrente."
            ),
        }

    return {
        "perfil": "EQUILIBRADO",
        "classe_cor": "green",
        "descricao": (
            "A composição não mostra concentração extrema. Ainda assim, é recomendável separar "
            "o patrimônio por objetivos: reserva, curto prazo, médio prazo e longo prazo."
        ),
    }


def gerar_alertas(distribuicao: list[dict]) -> list[dict]:
    alertas = []

    liquidez = buscar_classe(distribuicao, "LIQUIDEZ IMEDIATA")
    poupanca = buscar_classe(distribuicao, "POUPANÇA")
    cripto = buscar_classe(distribuicao, "CRIPTOATIVOS")
    renda_variavel = buscar_classe(distribuicao, "RENDA VARIÁVEL")
    dinheiro_fisico = buscar_classe(distribuicao, "DINHEIRO FÍSICO")

    if liquidez["percentual"] >= 35:
        alertas.append(
            {
                "tipo": "Excesso em liquidez imediata",
                "nivel": "atenção",
                "texto": (
                    "Há percentual elevado em contas ou aplicações de liquidez imediata. "
                    "Isso pode ser confortável, mas também pode indicar dinheiro parado "
                    "com baixa eficiência."
                ),
            }
        )

    if poupanca["percentual"] >= 25:
        alertas.append(
            {
                "tipo": "Concentração em poupança",
                "nivel": "atenção",
                "texto": (
                    "A poupança representa uma parcela relevante do patrimônio. "
                    "Vale comparar com alternativas conservadoras, como Tesouro Selic "
                    "e CDBs de liquidez diária."
                ),
            }
        )

    if cripto["percentual"] >= 10:
        alertas.append(
            {
                "tipo": "Exposição relevante em criptoativos",
                "nivel": "risco",
                "texto": (
                    "Criptoativos são voláteis. Se essa parcela estiver acima do limite "
                    "aceitável pelo cliente, pode haver risco de oscilação patrimonial elevada."
                ),
            }
        )

    if renda_variavel["percentual"] >= 35:
        alertas.append(
            {
                "tipo": "Alta exposição em renda variável",
                "nivel": "risco",
                "texto": (
                    "A renda variável representa parcela elevada do patrimônio. "
                    "É importante avaliar diversificação, prazo e tolerância a oscilações."
                ),
            }
        )

    if dinheiro_fisico["percentual"] >= 10:
        alertas.append(
            {
                "tipo": "Dinheiro físico elevado",
                "nivel": "atenção",
                "texto": (
                    "Valores relevantes em cofre ou em mãos podem reduzir eficiência financeira "
                    "e aumentar risco operacional. Parte pode ser direcionada a liquidez diária."
                ),
            }
        )

    if not alertas:
        alertas.append(
            {
                "tipo": "Sem concentração crítica",
                "nivel": "ok",
                "texto": (
                    "Não foram identificadas concentrações críticas pelas regras atuais. "
                    "Ainda assim, a alocação deve ser comparada com objetivos, prazo e perfil de risco."
                ),
            }
        )

    return alertas


def gerar_caminhos_investimento(
    distribuicao: list[dict],
    cenario_juros: dict,
) -> list[dict]:
    caminhos = []

    liquidez = buscar_classe(distribuicao, "LIQUIDEZ IMEDIATA")
    poupanca = buscar_classe(distribuicao, "POUPANÇA")
    cripto = buscar_classe(distribuicao, "CRIPTOATIVOS")
    renda_variavel = buscar_classe(distribuicao, "RENDA VARIÁVEL")
    dinheiro_fisico = buscar_classe(distribuicao, "DINHEIRO FÍSICO")

    liquidez_total = liquidez["percentual"] + poupanca["percentual"]

    caminhos.append(
        {
            "titulo": "1. Reserva de emergência",
            "prioridade": "Alta",
            "descricao": (
                "Antes de buscar rentabilidade, o cliente deve manter uma reserva de emergência "
                "em produto seguro, líquido e de baixa volatilidade."
            ),
            "indicacoes": [
                "Tesouro Selic",
                "CDB com liquidez diária e rendimento competitivo",
                "Conta remunerada confiável",
                "Fundo DI simples com baixa taxa, se fizer sentido",
            ],
        }
    )

    if liquidez["percentual"] > 25 or dinheiro_fisico["percentual"] > 8:
        caminhos.append(
            {
                "titulo": "2. Reduzir dinheiro parado",
                "prioridade": "Alta",
                "descricao": (
                    "Há valores relevantes em contas, cofre ou dinheiro físico. "
                    "Parte pode continuar líquida, mas com melhor organização e rendimento."
                ),
                "indicacoes": [
                    "Migrar excesso de conta corrente para liquidez diária",
                    "Concentrar reserva em produto com segurança e resgate rápido",
                    "Reduzir dinheiro físico ao mínimo operacional",
                ],
            }
        )

    if poupanca["percentual"] > 20:
        caminhos.append(
            {
                "titulo": "3. Comparar poupança com renda fixa eficiente",
                "prioridade": "Alta",
                "descricao": (
                    "A poupança é simples, mas pode perder eficiência em relação a alternativas "
                    "conservadoras, especialmente em cenário de juros elevados."
                ),
                "indicacoes": [
                    "Tesouro Selic para parte conservadora",
                    "CDB liquidez diária próximo ou acima de 100% do CDI",
                    "LCI/LCA quando a taxa líquida compensar e o prazo fizer sentido",
                ],
            }
        )

    if cenario_juros.get("nivel") == "JUROS ALTOS":
        caminhos.append(
            {
                "titulo": "4. Aproveitar renda fixa no cenário de juros altos",
                "prioridade": "Média",
                "descricao": (
                    "Com juros altos, aplicações pós-fixadas tendem a ser mais interessantes "
                    "para perfis conservadores e para dinheiro de curto prazo."
                ),
                "indicacoes": [
                    "Pós-fixados atrelados ao CDI",
                    "Tesouro Selic",
                    "CDBs de bancos sólidos ou com cobertura do FGC, observando limite e prazo",
                    "LCI/LCA para objetivos com prazo definido",
                ],
            }
        )

    if liquidez_total > 60:
        caminhos.append(
            {
                "titulo": "5. Separar patrimônio por objetivos",
                "prioridade": "Média",
                "descricao": (
                    "O patrimônio está muito defensivo. Depois da reserva, pode ser útil separar "
                    "o dinheiro em curto, médio e longo prazo."
                ),
                "indicacoes": [
                    "Curto prazo: Tesouro Selic ou CDB liquidez diária",
                    "Médio prazo: CDBs, LCI/LCA ou Tesouro IPCA de prazo compatível",
                    "Longo prazo: diversificação gradual conforme perfil",
                ],
            }
        )

    if renda_variavel["percentual"] < 10 and cripto["percentual"] < 5:
        caminhos.append(
            {
                "titulo": "6. Avaliar crescimento patrimonial de longo prazo",
                "prioridade": "Baixa",
                "descricao": (
                    "Se a reserva estiver formada e o cliente aceitar oscilações, pode avaliar "
                    "gradualmente alternativas de crescimento patrimonial."
                ),
                "indicacoes": [
                    "Tesouro IPCA+ para objetivos de longo prazo",
                    "ETFs ou fundos diversificados",
                    "Fundos imobiliários, se compatíveis com o perfil",
                    "Ações diversificadas apenas com estudo e tolerância a risco",
                ],
            }
        )

    if cripto["percentual"] > 8:
        caminhos.append(
            {
                "titulo": "7. Controlar exposição em criptoativos",
                "prioridade": "Alta",
                "descricao": (
                    "Criptoativos podem ter forte oscilação. Eles não devem compor reserva de emergência "
                    "e precisam respeitar limite definido pelo perfil do cliente."
                ),
                "indicacoes": [
                    "Definir percentual máximo para cripto",
                    "Evitar usar dinheiro de curto prazo",
                    "Rebalancear se a concentração crescer demais",
                ],
            }
        )

    return caminhos


def gerar_plano_realocacao(distribuicao: list[dict]) -> list[dict]:
    liquidez = buscar_classe(distribuicao, "LIQUIDEZ IMEDIATA")
    poupanca = buscar_classe(distribuicao, "POUPANÇA")
    cripto = buscar_classe(distribuicao, "CRIPTOATIVOS")
    dinheiro_fisico = buscar_classe(distribuicao, "DINHEIRO FÍSICO")

    passos = []

    passos.append(
        {
            "passo": "Definir reserva mínima",
            "detalhe": (
                "Separar o valor necessário para emergência antes de pensar em rentabilidade. "
                "O sistema pode evoluir depois para calcular essa reserva com base nas despesas mensais."
            ),
        }
    )

    if liquidez["percentual"] > 30:
        passos.append(
            {
                "passo": "Reorganizar excesso em conta",
                "detalhe": (
                    "Avaliar quanto da liquidez imediata precisa realmente ficar em conta corrente "
                    "e quanto poderia ir para produto com liquidez diária."
                ),
            }
        )

    if poupanca["percentual"] > 20:
        passos.append(
            {
                "passo": "Migrar poupança gradualmente",
                "detalhe": (
                    "Comparar poupança com Tesouro Selic, CDB liquidez diária e LCI/LCA, "
                    "sem fazer migração brusca e sem comprometer liquidez."
                ),
            }
        )

    if dinheiro_fisico["percentual"] > 5:
        passos.append(
            {
                "passo": "Reduzir dinheiro físico",
                "detalhe": (
                    "Manter apenas valor operacional em mãos/cofre e direcionar o restante "
                    "para produto seguro e rastreável."
                ),
            }
        )

    if cripto["percentual"] > 10:
        passos.append(
            {
                "passo": "Reavaliar cripto",
                "detalhe": (
                    "Definir limite máximo de exposição e avaliar rebalanceamento se o percentual "
                    "estiver acima do perfil de risco."
                ),
            }
        )

    passos.append(
        {
            "passo": "Separar objetivos",
            "detalhe": (
                "Depois da reserva, dividir o patrimônio entre curto prazo, médio prazo e longo prazo."
            ),
        }
    )

    return passos


def montar_analise_investimentos(
    ano: str | None = None,
    mes: str | None = None,
) -> dict:
    ano_final = str(ano or date.today().year)
    mes_final = mes or obter_mes_atual_sigla()

    resumo = montar_resumo_patrimonio(
        ano=ano_final,
        ano_resumo=ano_final,
        mes_resumo=mes_final,
    )

    ativos = resumo.get("ativos", [])
    distribuicao = montar_distribuicao_por_classe(ativos)

    mercado = obter_selic_anualizada_atual()
    cenario_juros = classificar_cenario_juros(float(mercado.get("selic_anual", 0) or 0))

    radar_mercado = montar_radar_mercado()

    perfil = definir_perfil_aproximado(distribuicao)
    alertas = gerar_alertas(distribuicao)
    caminhos = gerar_caminhos_investimento(distribuicao, cenario_juros)
    plano = gerar_plano_realocacao(distribuicao)

    return {
        "ano": ano_final,
        "mes": mes_final,
        "meses_opcoes": MESES_OPCOES,

        "resumo": resumo,
        "ativos": ativos,
        "distribuicao": distribuicao,

        "mercado": mercado,
        "cenario_juros": cenario_juros,
        "radar_mercado": radar_mercado,

        "perfil": perfil,
        "alertas": alertas,
        "caminhos": caminhos,
        "plano": plano,

        "tem_dados": bool(resumo.get("tem_dados_mes_resumo")),
        "aviso": (
            "As indicações são educativas e baseadas na composição patrimonial cadastrada "
            "e no cenário econômico consultado. Não substituem análise individualizada "
            "de profissional habilitado, nem representam garantia de rentabilidade."
        ),
    }