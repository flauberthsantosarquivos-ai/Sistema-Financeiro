from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao


def listar_lancamentos_mobile(ano: int | None = None, mes: int | None = None):
    """
    Retorna lançamentos simulados para a versão mobile.

    Na próxima fase, esta função será conectada à base real
    de lançamentos do Sistema Financeiro.
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
        "total": 4,
        "lancamentos": [
            {
                "id": 1,
                "data": f"{referencia}-01",
                "descricao": "Supermercado",
                "categoria": "Alimentação",
                "tipo": "despesa",
                "valor": 325.90,
                "forma_pagamento": "Cartão de crédito",
            },
            {
                "id": 2,
                "data": f"{referencia}-03",
                "descricao": "Salário",
                "categoria": "Renda",
                "tipo": "receita",
                "valor": 6200.00,
                "forma_pagamento": "Conta corrente",
            },
            {
                "id": 3,
                "data": f"{referencia}-05",
                "descricao": "Internet",
                "categoria": "Moradia",
                "tipo": "despesa",
                "valor": 119.90,
                "forma_pagamento": "Débito automático",
            },
            {
                "id": 4,
                "data": f"{referencia}-08",
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