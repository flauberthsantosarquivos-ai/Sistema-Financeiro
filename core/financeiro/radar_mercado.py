from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests


COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
BRAPI_QUOTE_URL = "https://brapi.dev/api/quote"


CRIPTOS_RADAR = [
    {
        "id": "bitcoin",
        "nome": "Bitcoin",
        "simbolo": "BTC",
        "categoria": "Cripto principal",
        "risco": "Alto",
        "observacao": (
            "Ativo mais consolidado do mercado cripto. Ainda é volátil e não deve ser usado "
            "como reserva de emergência."
        ),
    },
    {
        "id": "ethereum",
        "nome": "Ethereum",
        "simbolo": "ETH",
        "categoria": "Cripto principal / infraestrutura",
        "risco": "Alto",
        "observacao": (
            "Ativo relevante em infraestrutura blockchain. Pode oscilar bastante e exige horizonte "
            "de longo prazo e tolerância a risco."
        ),
    },
    {
        "id": "solana",
        "nome": "Solana",
        "simbolo": "SOL",
        "categoria": "Blockchain de alta performance",
        "risco": "Alto",
        "observacao": (
            "Ativo de maior volatilidade que BTC/ETH. Pode entrar em radar apenas para parcela "
            "arrojada e limitada."
        ),
    },
    {
        "id": "binancecoin",
        "nome": "BNB",
        "simbolo": "BNB",
        "categoria": "Exchange token / ecossistema",
        "risco": "Alto",
        "observacao": (
            "Token ligado ao ecossistema Binance. Deve ser avaliado com atenção a risco regulatório, "
            "liquidez e concentração."
        ),
    },
    {
        "id": "ripple",
        "nome": "XRP",
        "simbolo": "XRP",
        "categoria": "Cripto de pagamentos",
        "risco": "Alto",
        "observacao": (
            "Ativo com histórico de forte oscilação e influência de fatores regulatórios e jurídicos."
        ),
    },
    {
        "id": "bonk",
        "nome": "Bonk",
        "simbolo": "BONK",
        "categoria": "Memecoin / especulativo",
        "risco": "Muito alto",
        "observacao": (
            "Memecoin de alta volatilidade. Deve ser tratada como ativo especulativo, com percentual "
            "pequeno e dinheiro que o cliente aceite perder."
        ),
    },
    {
        "id": "gigachad-2",
        "nome": "GigaChad",
        "simbolo": "GIGA",
        "categoria": "Memecoin / especulativo",
        "risco": "Muito alto",
        "observacao": (
            "Ativo especulativo e muito volátil. Não deve compor reserva de emergência nem parcela "
            "central da carteira."
        ),
    },
]


ACOES_RADAR = [
    {
        "ticker": "PETR4",
        "nome": "Petrobras PN",
        "tipo": "Ação",
        "setor": "Petróleo, gás e energia",
        "risco": "Alto",
        "observacao": (
            "Ativo líquido da bolsa brasileira, sensível a petróleo, câmbio, política de preços, "
            "dividendos e risco estatal."
        ),
    },
    {
        "ticker": "VALE3",
        "nome": "Vale ON",
        "tipo": "Ação",
        "setor": "Mineração e commodities",
        "risco": "Alto",
        "observacao": (
            "Ativo ligado ao minério de ferro, China, dólar e ciclo global de commodities."
        ),
    },
    {
        "ticker": "ITUB4",
        "nome": "Itaú Unibanco PN",
        "tipo": "Ação",
        "setor": "Bancos",
        "risco": "Moderado/Alto",
        "observacao": (
            "Banco de grande porte e alta liquidez. Pode ser observado para exposição ao setor financeiro."
        ),
    },
    {
        "ticker": "BBAS3",
        "nome": "Banco do Brasil ON",
        "tipo": "Ação",
        "setor": "Bancos",
        "risco": "Moderado/Alto",
        "observacao": (
            "Banco com histórico de dividendos e influência de fatores macroeconômicos e governamentais."
        ),
    },
    {
        "ticker": "BBDC4",
        "nome": "Bradesco PN",
        "tipo": "Ação",
        "setor": "Bancos",
        "risco": "Moderado/Alto",
        "observacao": (
            "Ativo financeiro tradicional, sensível a crédito, inadimplência, margem financeira e ciclo econômico."
        ),
    },
    {
        "ticker": "WEGE3",
        "nome": "WEG ON",
        "tipo": "Ação",
        "setor": "Indústria / bens de capital",
        "risco": "Alto",
        "observacao": (
            "Empresa de qualidade reconhecida pelo mercado, mas geralmente exige atenção ao preço de entrada."
        ),
    },
    {
        "ticker": "BOVA11",
        "nome": "ETF Ibovespa",
        "tipo": "ETF",
        "setor": "Índice Brasil",
        "risco": "Moderado/Alto",
        "observacao": (
            "ETF que replica o Ibovespa. Serve como exposição ampla à bolsa brasileira, mas concentra risco Brasil."
        ),
    },
    {
        "ticker": "IVVB11",
        "nome": "ETF S&P 500",
        "tipo": "ETF",
        "setor": "Exterior / dólar",
        "risco": "Moderado/Alto",
        "observacao": (
            "ETF com exposição ao mercado americano e ao dólar. Pode ajudar na diversificação internacional."
        ),
    },
    {
        "ticker": "MXRF11",
        "nome": "Maxi Renda FII",
        "tipo": "FII",
        "setor": "Fundo imobiliário / papel",
        "risco": "Moderado",
        "observacao": (
            "FII popular de recebíveis. Deve ser avaliado por qualidade da carteira, dividendos, risco de crédito e preço."
        ),
    },
    {
        "ticker": "HGLG11",
        "nome": "CSHG Logística FII",
        "tipo": "FII",
        "setor": "Fundo imobiliário / logística",
        "risco": "Moderado",
        "observacao": (
            "FII de logística. Deve ser analisado por vacância, qualidade dos imóveis, contratos e preço da cota."
        ),
    },
]


# Lista reduzida usada quando NÃO houver BRAPI_TOKEN.
# A ideia é permitir que o radar funcione agora, sem token,
# usando os ativos geralmente liberados/teste na brapi.
ACOES_RADAR_SEM_TOKEN = [
    {
        "ticker": "PETR4",
        "nome": "Petrobras PN",
        "tipo": "Ação",
        "setor": "Petróleo, gás e energia",
        "risco": "Alto",
        "observacao": (
            "Ativo líquido da bolsa brasileira, sensível a petróleo, câmbio, política de preços, "
            "dividendos e risco estatal."
        ),
    },
    {
        "ticker": "MGLU3",
        "nome": "Magazine Luiza ON",
        "tipo": "Ação",
        "setor": "Varejo",
        "risco": "Alto",
        "observacao": (
            "Ativo de varejo com alta volatilidade, sensível a juros, consumo, crédito "
            "e expectativa de crescimento."
        ),
    },
    {
        "ticker": "VALE3",
        "nome": "Vale ON",
        "tipo": "Ação",
        "setor": "Mineração e commodities",
        "risco": "Alto",
        "observacao": (
            "Ativo ligado ao minério de ferro, China, dólar e ciclo global de commodities."
        ),
    },
    {
        "ticker": "ITUB4",
        "nome": "Itaú Unibanco PN",
        "tipo": "Ação",
        "setor": "Bancos",
        "risco": "Moderado/Alto",
        "observacao": (
            "Banco de grande porte e alta liquidez. Pode ser observado para exposição ao setor financeiro."
        ),
    },
]


def formatar_moeda_brl(valor: Any) -> str:
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0

    texto = f"R$ {numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero(valor: Any) -> str:
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0

    texto = f"{numero:,.0f}"
    return texto.replace(",", ".")


def formatar_percentual(valor: Any) -> str:
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0

    sinal = "+" if numero > 0 else ""
    return f"{sinal}{numero:.2f}%".replace(".", ",")


def classificar_tendencia(variacao_24h: float | None) -> dict:
    if variacao_24h is None:
        return {
            "tendencia": "Sem dados",
            "classe": "neutra",
            "comentario": "Não foi possível calcular a tendência de curto prazo.",
        }

    if variacao_24h >= 8:
        return {
            "tendencia": "Alta forte",
            "classe": "alta",
            "comentario": (
                "Alta expressiva no período analisado. Pode indicar força compradora, "
                "mas também exige cuidado com entrada tardia após movimento acelerado."
            ),
        }

    if variacao_24h >= 3:
        return {
            "tendencia": "Alta moderada",
            "classe": "alta",
            "comentario": (
                "Movimento positivo relevante. Vale acompanhar volume, contexto e continuidade "
                "antes de qualquer decisão."
            ),
        }

    if variacao_24h > -3:
        return {
            "tendencia": "Neutra / lateral",
            "classe": "neutra",
            "comentario": (
                "Sem movimento forte no curto prazo. Melhor avaliar tendência em prazo maior, "
                "fundamentos, volume e posição dentro da carteira."
            ),
        }

    if variacao_24h > -8:
        return {
            "tendencia": "Queda moderada",
            "classe": "queda",
            "comentario": (
                "Queda relevante no curto prazo. Pode representar correção, mas não deve ser "
                "tratada automaticamente como oportunidade."
            ),
        }

    return {
        "tendencia": "Queda forte",
        "classe": "queda",
        "comentario": (
            "Queda expressiva no período analisado. Exige cautela, pois pode haver aumento "
            "de volatilidade e risco de continuidade da queda."
        ),
    }


def montar_orientacao_cripto(
    ativo_base: dict,
    variacao_24h: float | None,
    posicao_market_cap: int | None,
) -> str:
    risco = ativo_base.get("risco", "")

    if risco == "Muito alto":
        return (
            "Ativo altamente especulativo. Só faria sentido para perfil arrojado, com percentual pequeno "
            "do patrimônio, sem comprometer reserva de emergência e aceitando forte volatilidade."
        )

    if posicao_market_cap and posicao_market_cap <= 2:
        return (
            "Ativo cripto principal. Pode entrar no radar de longo prazo para cliente com perfil compatível, "
            "mas deve respeitar limite percentual e não substituir renda fixa ou reserva."
        )

    if variacao_24h is not None and variacao_24h >= 8:
        return (
            "Ativo em forte alta recente. Evitar decisão por impulso; acompanhar se o movimento tem volume "
            "e se faz sentido dentro do percentual máximo de cripto do cliente."
        )

    if variacao_24h is not None and variacao_24h <= -8:
        return (
            "Ativo em queda forte recente. Pode haver volatilidade elevada; evitar aumentar exposição sem "
            "estratégia clara e limite de perda."
        )

    return (
        "Ativo de risco elevado. Avaliar apenas como parte pequena e diversificada da carteira, depois da "
        "reserva de emergência formada."
    )


def montar_orientacao_acao(
    ativo_base: dict,
    variacao: float | None,
    liquidez_valor: float | None,
) -> str:
    tipo = ativo_base.get("tipo", "")
    ticker = ativo_base.get("ticker", "")

    if tipo == "ETF":
        if ticker == "IVVB11":
            return (
                "ETF útil para diversificação internacional e exposição ao dólar. Pode fazer sentido "
                "para longo prazo, especialmente se o patrimônio estiver muito concentrado no Brasil."
            )

        return (
            "ETF de exposição ampla. Pode ser mais simples que escolher ações individuais, mas ainda "
            "exige tolerância à volatilidade da bolsa."
        )

    if tipo == "FII":
        return (
            "Fundo imobiliário pode ajudar na geração de renda e diversificação, mas deve ser avaliado "
            "por vacância, qualidade da carteira, dividendos, endividamento e sensibilidade aos juros."
        )

    if ticker == "MGLU3":
        return (
            "Ativo de varejo mais especulativo e sensível ao ciclo de juros, consumo e crédito. "
            "Pode servir como estudo de renda variável, mas exige cautela e não deve ser tratado "
            "como alternativa conservadora."
        )

    if variacao is not None and variacao >= 5:
        return (
            "Ativo em alta relevante. Evitar entrada apenas por euforia; avaliar fundamentos, preço, "
            "setor e se o movimento já não precificou boa parte da notícia."
        )

    if variacao is not None and variacao <= -5:
        return (
            "Ativo em queda relevante. Pode entrar no radar para estudo, mas queda isolada não significa "
            "oportunidade. É preciso avaliar motivo da queda, fundamentos e risco."
        )

    if liquidez_valor is not None and liquidez_valor > 0:
        return (
            "Ativo líquido e relevante para acompanhamento. Pode entrar no radar, mas a decisão deve "
            "considerar perfil de risco, diversificação, fundamentos e preço de entrada."
        )

    return (
        "Ativo em radar para estudo. Antes de qualquer alocação, avaliar fundamentos, liquidez, setor, "
        "risco e aderência ao perfil do cliente."
    )


def buscar_radar_cripto_coingecko() -> dict:
    ids = ",".join([item["id"] for item in CRIPTOS_RADAR])
    mapa_base = {item["id"]: item for item in CRIPTOS_RADAR}

    params = {
        "vs_currency": "brl",
        "ids": ids,
        "order": "market_cap_desc",
        "per_page": len(CRIPTOS_RADAR),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h,7d,30d",
        "locale": "pt",
    }

    try:
        resposta = requests.get(
            COINGECKO_MARKETS_URL,
            params=params,
            timeout=12,
            headers={
                "accept": "application/json",
                "User-Agent": "Sistema-Financeiro/1.0",
            },
        )
        resposta.raise_for_status()
        dados = resposta.json()

        if not isinstance(dados, list):
            raise ValueError("Resposta inesperada da CoinGecko.")

        ativos = []

        for item in dados:
            ativo_id = item.get("id")
            base = mapa_base.get(ativo_id, {})

            variacao_24h = item.get("price_change_percentage_24h")
            variacao_7d = item.get("price_change_percentage_7d_in_currency")
            variacao_30d = item.get("price_change_percentage_30d_in_currency")
            market_cap_rank = item.get("market_cap_rank")

            tendencia = classificar_tendencia(variacao_24h)

            ativos.append(
                {
                    "id": ativo_id,
                    "nome": base.get("nome") or item.get("name") or ativo_id,
                    "simbolo": base.get("simbolo") or str(item.get("symbol", "")).upper(),
                    "categoria": base.get("categoria", "Criptoativo"),
                    "risco": base.get("risco", "Alto"),
                    "preco": float(item.get("current_price") or 0),
                    "preco_fmt": formatar_moeda_brl(item.get("current_price")),
                    "market_cap": float(item.get("market_cap") or 0),
                    "market_cap_fmt": formatar_moeda_brl(item.get("market_cap")),
                    "volume_24h": float(item.get("total_volume") or 0),
                    "volume_24h_fmt": formatar_moeda_brl(item.get("total_volume")),
                    "rank": market_cap_rank,
                    "rank_fmt": f"#{market_cap_rank}" if market_cap_rank else "-",
                    "variacao_24h": float(variacao_24h or 0),
                    "variacao_24h_fmt": formatar_percentual(variacao_24h),
                    "variacao_7d": float(variacao_7d or 0),
                    "variacao_7d_fmt": formatar_percentual(variacao_7d),
                    "variacao_30d": float(variacao_30d or 0),
                    "variacao_30d_fmt": formatar_percentual(variacao_30d),
                    "tendencia": tendencia,
                    "comentario": tendencia["comentario"],
                    "orientacao": montar_orientacao_cripto(
                        ativo_base=base,
                        variacao_24h=variacao_24h,
                        posicao_market_cap=market_cap_rank,
                    ),
                    "observacao": base.get("observacao", ""),
                }
            )

        ids_retornados = {item["id"] for item in ativos}
        faltantes = [
            mapa_base[cripto_id]["nome"]
            for cripto_id in mapa_base
            if cripto_id not in ids_retornados
        ]

        return {
            "ok": True,
            "fonte": "CoinGecko /coins/markets",
            "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "ativos": ativos,
            "faltantes": faltantes,
            "mensagem": "Radar cripto atualizado com dados reais de mercado.",
        }

    except Exception as e:
        return {
            "ok": False,
            "fonte": "CoinGecko /coins/markets",
            "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "ativos": [],
            "faltantes": [item["nome"] for item in CRIPTOS_RADAR],
            "mensagem": f"Não foi possível consultar o radar cripto: {e}",
        }


def buscar_radar_acoes_brapi() -> dict:
    token = os.getenv("BRAPI_TOKEN", "").strip()

    # Sem token, usa apenas ativos de teste/liberação gratuita.
    # Com token, usa a lista completa com ações, ETFs e FIIs.
    lista_ativos = ACOES_RADAR if token else ACOES_RADAR_SEM_TOKEN

    tickers = ",".join([item["ticker"] for item in lista_ativos])
    mapa_base = {item["ticker"]: item for item in lista_ativos}

    params = {
        "range": "1d",
        "interval": "1d",
        "fundamental": "false",
        "dividends": "false",
    }

    if token:
        params["token"] = token

    url = f"{BRAPI_QUOTE_URL}/{tickers}"

    try:
        resposta = requests.get(
            url,
            params=params,
            timeout=12,
            headers={
                "accept": "application/json",
                "User-Agent": "Sistema-Financeiro/1.0",
            },
        )
        resposta.raise_for_status()
        dados = resposta.json()

        resultados = dados.get("results", [])

        if not isinstance(resultados, list):
            raise ValueError("Resposta inesperada da brapi.")

        ativos = []

        for item in resultados:
            ticker = str(item.get("symbol", "") or "").upper()
            base = mapa_base.get(ticker, {})

            preco = item.get("regularMarketPrice")
            variacao = item.get("regularMarketChangePercent")
            volume = item.get("regularMarketVolume")
            nome_curto = item.get("shortName") or item.get("longName") or base.get("nome") or ticker

            tendencia = classificar_tendencia(variacao)

            ativos.append(
                {
                    "ticker": ticker,
                    "nome": base.get("nome") or nome_curto,
                    "nome_mercado": nome_curto,
                    "tipo": base.get("tipo", "Ativo"),
                    "setor": base.get("setor", "Mercado"),
                    "risco": base.get("risco", "Moderado/Alto"),
                    "preco": float(preco or 0),
                    "preco_fmt": formatar_moeda_brl(preco),
                    "variacao": float(variacao or 0),
                    "variacao_fmt": formatar_percentual(variacao),
                    "volume": float(volume or 0),
                    "volume_fmt": formatar_numero(volume),
                    "tendencia": tendencia,
                    "comentario": tendencia["comentario"],
                    "orientacao": montar_orientacao_acao(
                        ativo_base=base,
                        variacao=variacao,
                        liquidez_valor=volume,
                    ),
                    "observacao": base.get("observacao", ""),
                    "moeda": item.get("currency", "BRL"),
                    "fonte_nome": item.get("longName") or item.get("shortName") or ticker,
                }
            )

        tickers_retornados = {item["ticker"] for item in ativos}
        faltantes = [
            ticker
            for ticker in mapa_base
            if ticker not in tickers_retornados
        ]

        if token:
            mensagem = "Radar de ações, ETFs e FIIs atualizado com dados reais de mercado."
        else:
            mensagem = (
                "Radar de ações atualizado com lista reduzida sem token. "
                "Para liberar ETFs, FIIs e lista completa, configure a variável BRAPI_TOKEN."
            )

        return {
            "ok": True,
            "fonte": "brapi /api/quote",
            "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "ativos": ativos,
            "faltantes": faltantes,
            "mensagem": mensagem,
            "usa_token": bool(token),
        }

    except Exception as e:
        return {
            "ok": False,
            "fonte": "brapi /api/quote",
            "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "ativos": [],
            "faltantes": [item["ticker"] for item in lista_ativos],
            "mensagem": f"Não foi possível consultar o radar de ações: {e}",
            "usa_token": bool(token),
        }


def gerar_leitura_radar_cripto(radar: dict) -> list[dict]:
    ativos = radar.get("ativos", [])

    if not ativos:
        return [
            {
                "titulo": "Radar cripto indisponível",
                "texto": (
                    "Não foi possível carregar dados de mercado neste momento. "
                    "Verifique conexão com a internet ou limitação temporária da API."
                ),
                "nivel": "atenção",
            }
        ]

    leituras = []

    altas_fortes = [
        item for item in ativos
        if float(item.get("variacao_24h", 0) or 0) >= 8
    ]

    quedas_fortes = [
        item for item in ativos
        if float(item.get("variacao_24h", 0) or 0) <= -8
    ]

    especulativos = [
        item for item in ativos
        if item.get("risco") == "Muito alto"
    ]

    if altas_fortes:
        nomes = ", ".join([item["nome"] for item in altas_fortes])
        leituras.append(
            {
                "titulo": "Criptos com alta forte no curto prazo",
                "texto": (
                    f"{nomes} aparecem com alta forte nas últimas 24h. "
                    "Isso pode indicar força, mas também aumenta o risco de entrada por impulso."
                ),
                "nivel": "atenção",
            }
        )

    if quedas_fortes:
        nomes = ", ".join([item["nome"] for item in quedas_fortes])
        leituras.append(
            {
                "titulo": "Criptos com queda forte no curto prazo",
                "texto": (
                    f"{nomes} aparecem com queda forte nas últimas 24h. "
                    "Pode haver volatilidade elevada; queda não é automaticamente oportunidade."
                ),
                "nivel": "risco",
            }
        )

    if especulativos:
        nomes = ", ".join([item["nome"] for item in especulativos])
        leituras.append(
            {
                "titulo": "Ativos especulativos no radar",
                "texto": (
                    f"{nomes} são tratados como ativos de risco muito alto. "
                    "Devem ser limitados a percentual pequeno e nunca usados como reserva."
                ),
                "nivel": "risco",
            }
        )

    if not leituras:
        leituras.append(
            {
                "titulo": "Radar cripto sem extremos relevantes",
                "texto": (
                    "Não foram identificados movimentos extremos entre os ativos acompanhados. "
                    "Mesmo assim, cripto continua sendo classe de alto risco."
                ),
                "nivel": "ok",
            }
        )

    return leituras


def gerar_leitura_radar_acoes(radar: dict) -> list[dict]:
    ativos = radar.get("ativos", [])

    if not ativos:
        return [
            {
                "titulo": "Radar de ações indisponível",
                "texto": (
                    "Não foi possível carregar dados de ações, ETFs e FIIs neste momento. "
                    "Verifique a internet, o limite da API ou configure a variável BRAPI_TOKEN."
                ),
                "nivel": "atenção",
            }
        ]

    leituras = []

    altas = [
        item for item in ativos
        if float(item.get("variacao", 0) or 0) >= 5
    ]

    quedas = [
        item for item in ativos
        if float(item.get("variacao", 0) or 0) <= -5
    ]

    etfs = [
        item for item in ativos
        if item.get("tipo") == "ETF"
    ]

    fiis = [
        item for item in ativos
        if item.get("tipo") == "FII"
    ]

    varejo = [
        item for item in ativos
        if item.get("setor") == "Varejo"
    ]

    if altas:
        nomes = ", ".join([item["ticker"] for item in altas])
        leituras.append(
            {
                "titulo": "Ativos em alta relevante",
                "texto": (
                    f"{nomes} aparecem com alta relevante. Isso pode indicar força, mas não deve "
                    "ser usado sozinho como sinal de compra."
                ),
                "nivel": "atenção",
            }
        )

    if quedas:
        nomes = ", ".join([item["ticker"] for item in quedas])
        leituras.append(
            {
                "titulo": "Ativos em queda relevante",
                "texto": (
                    f"{nomes} aparecem com queda relevante. Pode ser apenas correção ou reflexo "
                    "de notícia negativa; exige análise antes de qualquer decisão."
                ),
                "nivel": "risco",
            }
        )

    if etfs:
        leituras.append(
            {
                "titulo": "ETFs no radar para diversificação",
                "texto": (
                    "BOVA11 e IVVB11 ajudam a observar exposição ampla à bolsa brasileira e ao exterior. "
                    "Podem ser úteis para diversificação, respeitando perfil e prazo."
                ),
                "nivel": "ok",
            }
        )

    if fiis:
        leituras.append(
            {
                "titulo": "FIIs no radar para renda e diversificação",
                "texto": (
                    "Fundos imobiliários podem gerar renda recorrente, mas são sensíveis a juros, "
                    "vacância, qualidade dos imóveis e preço das cotas."
                ),
                "nivel": "atenção",
            }
        )

    if varejo:
        nomes = ", ".join([item["ticker"] for item in varejo])
        leituras.append(
            {
                "titulo": "Varejo no radar",
                "texto": (
                    f"{nomes} aparece no radar como ativo sensível a juros, consumo, crédito "
                    "e expectativa de crescimento. É uma classe mais volátil e exige cautela."
                ),
                "nivel": "atenção",
            }
        )

    if not leituras:
        leituras.append(
            {
                "titulo": "Radar de ações sem extremos relevantes",
                "texto": (
                    "Não foram identificados movimentos extremos nos ativos acompanhados. "
                    "O foco deve ser fundamentos, diversificação e aderência ao perfil."
                ),
                "nivel": "ok",
            }
        )

    return leituras


def montar_radar_mercado() -> dict:
    radar_cripto = buscar_radar_cripto_coingecko()
    leituras_cripto = gerar_leitura_radar_cripto(radar_cripto)

    radar_acoes = buscar_radar_acoes_brapi()
    leituras_acoes = gerar_leitura_radar_acoes(radar_acoes)

    return {
        "cripto": radar_cripto,
        "leituras_cripto": leituras_cripto,
        "acoes": radar_acoes,
        "leituras_acoes": leituras_acoes,
        "aviso": (
            "O radar usa dados públicos de mercado e serve como apoio educativo. "
            "Não representa recomendação de compra ou venda, nem garantia de rentabilidade."
        ),
    }