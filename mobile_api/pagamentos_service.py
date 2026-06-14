def listar_pagamentos_mobile():
    """
    Retorna pagamentos simulados para a versão mobile.
    """

    return {
        "mes": "2026-06",
        "total_pendente": 1370.00,
        "quantidade_pendente": 3,
        "pagamentos": [
            {
                "id": 1,
                "vencimento": "2026-06-10",
                "descricao": "Energia",
                "categoria": "Moradia",
                "valor": 280.00,
                "status": "pendente",
            },
            {
                "id": 2,
                "vencimento": "2026-06-12",
                "descricao": "Internet",
                "categoria": "Moradia",
                "valor": 119.90,
                "status": "pendente",
            },
            {
                "id": 3,
                "vencimento": "2026-06-15",
                "descricao": "Cartão de crédito",
                "categoria": "Cartão",
                "valor": 970.10,
                "status": "pendente",
            },
        ],
    }


def marcar_pagamento_como_pago_mobile(pagamento_id: int):
    """
    Simula a marcação de pagamento como pago pelo app mobile.
    """

    return {
        "status": "sucesso",
        "mensagem": "Pagamento marcado como pago pela API mobile",
        "pagamento_id": pagamento_id,
    }