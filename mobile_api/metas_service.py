from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao


def listar_metas_mobile(ano: int | None = None, mes: int | None = None):
    """
    Retorna metas simuladas para a versão mobile.
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
        "metas": [
            {
                "id": 1,
                "nome": "Reserva de emergência",
                "valor_atual": 7200.00,
                "valor_alvo": 10000.00,
                "percentual": 72.00,
                "status": "em_andamento",
            },
            {
                "id": 2,
                "nome": "Viagem",
                "valor_atual": 1800.00,
                "valor_alvo": 5000.00,
                "percentual": 36.00,
                "status": "em_andamento",
            },
            {
                "id": 3,
                "nome": "Quitar cartão",
                "valor_atual": 1500.00,
                "valor_alvo": 3000.00,
                "percentual": 50.00,
                "status": "em_andamento",
            },
        ],
    }