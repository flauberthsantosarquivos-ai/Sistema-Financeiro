def obter_dashboard_mobile():
    """
    Retorna os dados iniciais do dashboard mobile.

    Nesta fase, os dados ainda são simulados.
    Na próxima etapa, esta função será conectada aos dados reais
    do Sistema Financeiro.
    """

    return {
        "mes": "2026-06",
        "saldo_mes": 1250.75,
        "receitas": 6200.00,
        "despesas": 4949.25,
        "contas_pendentes": 8,
        "total_pendente": 1370.00,
        "patrimonio_total": 38500.00,
        "meta_principal": {
            "nome": "Reserva de emergência",
            "valor_atual": 7200.00,
            "valor_alvo": 10000.00,
            "percentual": 72,
        },
        "cards": [
            {
                "titulo": "Saldo do mês",
                "valor": 1250.75,
                "tipo": "saldo",
                "icone": "wallet",
            },
            {
                "titulo": "Receitas",
                "valor": 6200.00,
                "tipo": "receita",
                "icone": "arrow_down",
            },
            {
                "titulo": "Despesas",
                "valor": 4949.25,
                "tipo": "despesa",
                "icone": "arrow_up",
            },
            {
                "titulo": "Contas pendentes",
                "valor": 1370.00,
                "quantidade": 8,
                "tipo": "pagamentos",
                "icone": "calendar",
            },
            {
                "titulo": "Patrimônio",
                "valor": 38500.00,
                "tipo": "patrimonio",
                "icone": "chart",
            },
            {
                "titulo": "Meta principal",
                "valor": 7200.00,
                "valor_alvo": 10000.00,
                "percentual": 72,
                "tipo": "meta",
                "icone": "target",
            },
        ],
        "acoes_rapidas": [
            {
                "titulo": "Lançar despesa",
                "tipo": "despesa",
                "rota": "/lancamento/despesa",
            },
            {
                "titulo": "Lançar receita",
                "tipo": "receita",
                "rota": "/lancamento/receita",
            },
            {
                "titulo": "Ver pagamentos",
                "tipo": "pagamentos",
                "rota": "/pagamentos",
            },
            {
                "titulo": "Ver metas",
                "tipo": "metas",
                "rota": "/metas",
            },
        ],
    }