from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao


def obter_dashboard_mobile(ano: int | None = None, mes: int | None = None):
    """
    Retorna os dados do dashboard mobile.

    Nesta fase, os dados ainda são simulados, mas a estrutura
    já está preparada para receber ano e mês e depois ser ligada
    aos dados reais do Sistema Financeiro.
    """

    ano, mes = obter_periodo_padrao(ano, mes)
    referencia = montar_referencia(ano, mes)

    saldo_mes = 1250.75
    receitas = 6200.00
    despesas = 4949.25
    contas_pendentes = 8
    total_pendente = 1370.00
    patrimonio_total = 38500.00

    meta_principal = {
        "nome": "Reserva de emergência",
        "valor_atual": 7200.00,
        "valor_alvo": 10000.00,
        "percentual": 72,
    }

    return {
        "mes": referencia,
        "periodo": {
            "ano": ano,
            "mes": mes,
            "referencia": referencia,
        },
        "saldo_mes": saldo_mes,
        "receitas": receitas,
        "despesas": despesas,
        "contas_pendentes": contas_pendentes,
        "total_pendente": total_pendente,
        "patrimonio_total": patrimonio_total,
        "meta_principal": meta_principal,
        "cards": [
            {
                "titulo": "Saldo do mês",
                "valor": saldo_mes,
                "tipo": "saldo",
                "icone": "wallet",
            },
            {
                "titulo": "Receitas",
                "valor": receitas,
                "tipo": "receita",
                "icone": "arrow_down",
            },
            {
                "titulo": "Despesas",
                "valor": despesas,
                "tipo": "despesa",
                "icone": "arrow_up",
            },
            {
                "titulo": "Contas pendentes",
                "valor": total_pendente,
                "quantidade": contas_pendentes,
                "tipo": "pagamentos",
                "icone": "calendar",
            },
            {
                "titulo": "Patrimônio",
                "valor": patrimonio_total,
                "tipo": "patrimonio",
                "icone": "chart",
            },
            {
                "titulo": "Meta principal",
                "valor": meta_principal["valor_atual"],
                "valor_alvo": meta_principal["valor_alvo"],
                "percentual": meta_principal["percentual"],
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