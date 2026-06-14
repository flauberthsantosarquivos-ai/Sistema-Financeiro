from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao


def listar_pagamentos_mobile(ano: int | None = None, mes: int | None = None):
    """
    Retorna pagamentos simulados para a versão mobile.
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
        "total_pendente": 1370.00,
        "quantidade_pendente": 3,
        "pagamentos": [
            {
                "id": 1,
                "vencimento": f"{referencia}-10",
                "descricao": "Energia",
                "categoria": "Moradia",
                "valor": 280.00,
                "status": "pendente",
            },
            {
                "id": 2,
                "vencimento": f"{referencia}-12",
                "descricao": "Internet",
                "categoria": "Moradia",
                "valor": 119.90,
                "status": "pendente",
            },
            {
                "id": 3,
                "vencimento": f"{referencia}-15",
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