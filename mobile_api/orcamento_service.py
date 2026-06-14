def obter_orcamento_mobile():
    """
    Retorna orçamento simulado para a versão mobile.
    """

    return {
        "mes": "2026-06",
        "orcamento_total": 5000.00,
        "gasto_total": 3420.50,
        "percentual_usado": 68.41,
        "categorias": [
            {
                "categoria": "Alimentação",
                "orcado": 1200.00,
                "gasto": 980.00,
                "percentual": 81.67,
            },
            {
                "categoria": "Moradia",
                "orcado": 1800.00,
                "gasto": 1450.00,
                "percentual": 80.56,
            },
            {
                "categoria": "Transporte",
                "orcado": 700.00,
                "gasto": 430.50,
                "percentual": 61.50,
            },
            {
                "categoria": "Lazer",
                "orcado": 500.00,
                "gasto": 210.00,
                "percentual": 42.00,
            },
        ],
    }