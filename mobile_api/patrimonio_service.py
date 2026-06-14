from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao


def obter_patrimonio_mobile(ano: int | None = None, mes: int | None = None):
    """
    Retorna patrimônio simulado para a versão mobile.
    """

    ano, mes = obter_periodo_padrao(ano, mes)
    referencia = montar_referencia(ano, mes)

    return {
        "mes": referencia,
        "periodo": {
            "ano": ano,
            "mes": mes,
            "referencia": referencia,
        },
        "patrimonio_total": 38500.00,
        "variacao_mes": 1250.00,
        "percentual_variacao": 3.36,
        "itens": [
            {
                "grupo": "Contas",
                "descricao": "Conta corrente",
                "valor": 4500.00,
            },
            {
                "grupo": "Reserva",
                "descricao": "Poupança / Reserva",
                "valor": 12000.00,
            },
            {
                "grupo": "Investimentos",
                "descricao": "Renda fixa",
                "valor": 18000.00,
            },
            {
                "grupo": "Bens",
                "descricao": "Outros bens",
                "valor": 4000.00,
            },
        ],
    }