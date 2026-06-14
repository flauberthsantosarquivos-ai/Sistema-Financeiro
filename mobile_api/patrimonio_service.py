def obter_patrimonio_mobile():
    """
    Retorna patrimônio simulado para a versão mobile.
    """

    return {
        "mes": "2026-06",
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