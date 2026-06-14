def listar_metas_mobile():
    """
    Retorna metas simuladas para a versão mobile.
    """

    return {
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