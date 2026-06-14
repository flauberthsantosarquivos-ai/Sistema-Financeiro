def listar_lancamentos_mobile():
    """
    Retorna lançamentos simulados para a versão mobile.

    Na próxima fase, esta função será conectada à base real
    de lançamentos do Sistema Financeiro.
    """

    return {
        "mes": "2026-06",
        "total": 4,
        "lancamentos": [
            {
                "id": 1,
                "data": "2026-06-01",
                "descricao": "Supermercado",
                "categoria": "Alimentação",
                "tipo": "despesa",
                "valor": 325.90,
                "forma_pagamento": "Cartão de crédito",
            },
            {
                "id": 2,
                "data": "2026-06-03",
                "descricao": "Salário",
                "categoria": "Renda",
                "tipo": "receita",
                "valor": 6200.00,
                "forma_pagamento": "Conta corrente",
            },
            {
                "id": 3,
                "data": "2026-06-05",
                "descricao": "Internet",
                "categoria": "Moradia",
                "tipo": "despesa",
                "valor": 119.90,
                "forma_pagamento": "Débito automático",
            },
            {
                "id": 4,
                "data": "2026-06-08",
                "descricao": "Combustível",
                "categoria": "Transporte",
                "tipo": "despesa",
                "valor": 220.00,
                "forma_pagamento": "Cartão de crédito",
            },
        ],
    }


def criar_lancamento_mobile(dados: dict):
    """
    Simula o cadastro de um novo lançamento pelo app mobile.
    """

    return {
        "status": "sucesso",
        "mensagem": "Lançamento recebido pela API mobile",
        "dados_recebidos": dados,
    }