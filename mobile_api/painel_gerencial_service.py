from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao

from core.financeiro.dashboard_base import filtrar_por_periodo, ler_base_lancamentos
from core.financeiro.orcamento_google import ler_orcamento_mensal
from Web_app.routes_financeiro import (
    ORDEM_MESES,
    filtrar_orcamento_por_periodo,
    preparar_analise,
)


def _mes_numero_para_sigla(mes: int) -> str:
    """
    Converte mês numérico para a sigla usada no Painel Gerencial web.
    Exemplo:
    1 -> JAN
    6 -> JUN
    12 -> DEZ
    """

    if 1 <= mes <= 12:
        return ORDEM_MESES[mes - 1]

    return ORDEM_MESES[0]


def obter_painel_gerencial_mobile(
    ano: int | None = None,
    mes: int | None = None,
):
    """
    Retorna somente os cards iniciais reais do Painel Gerencial
    para uso no app mobile.

    Esta versão é propositalmente resumida para o celular.
    Os detalhamentos serão criados em rotas próprias depois.
    """

    ano, mes = obter_periodo_padrao(ano, mes)
    referencia = montar_referencia(ano, mes)
    ano_texto = str(ano)
    mes_sigla = _mes_numero_para_sigla(mes)

    registros = ler_base_lancamentos()
    registros_orcamento_todos = ler_orcamento_mensal()

    registros_filtrados = filtrar_por_periodo(
        registros=registros,
        periodo_tipo="mes_unico",
        mes_unico=mes_sigla,
        mes_inicio="JAN",
        mes_fim="DEZ",
        ano=ano_texto,
    )

    registros_orcamento_filtrados = filtrar_orcamento_por_periodo(
        registros_orcamento=registros_orcamento_todos,
        periodo_tipo="mes_unico",
        mes_unico=mes_sigla,
        mes_inicio="JAN",
        mes_fim="DEZ",
        ano=ano_texto,
    )

    registros_ano = filtrar_por_periodo(
        registros=registros,
        periodo_tipo="todos",
        mes_unico=mes_sigla,
        mes_inicio="JAN",
        mes_fim="DEZ",
        ano=ano_texto,
    )

    analise = preparar_analise(
        registros=registros_filtrados,
        registros_ano=registros_ano,
        registros_orcamento=registros_orcamento_filtrados,
    )

    total_receitas = float(analise.get("total_receitas", 0.0) or 0.0)
    total_despesas = float(analise.get("total_despesas", 0.0) or 0.0)
    total_investimentos = float(analise.get("total_investimentos", 0.0) or 0.0)
    saldo = float(analise.get("saldo", 0.0) or 0.0)
    disponivel_apos_investimentos = float(
        analise.get("disponivel_apos_investimentos", 0.0) or 0.0
    )
    comprometimento = float(analise.get("comprometimento", 0.0) or 0.0)
    percentual_investimento_receita = float(
        analise.get("percentual_investimento_receita", 0.0) or 0.0
    )

    total_lancamentos = int(analise.get("total_lancamentos", 0) or 0)
    qtd_receitas = int(analise.get("qtd_receitas", 0) or 0)
    qtd_despesas = int(analise.get("qtd_despesas", 0) or 0)
    qtd_investimentos = int(analise.get("qtd_investimentos", 0) or 0)
    qtd_a_classificar = int(analise.get("qtd_a_classificar", 0) or 0)

    maior_categoria = analise.get("maior_categoria", "Sem despesas")
    maior_categoria_valor = float(analise.get("maior_categoria_valor", 0.0) or 0.0)

    return {
        "mes": referencia,
        "periodo": {
            "ano": ano,
            "mes": mes,
            "mes_sigla": mes_sigla,
            "referencia": referencia,
        },
        "resumo": {
            "receitas": total_receitas,
            "despesas": total_despesas,
            "investimentos": total_investimentos,
            "saldo": saldo,
            "disponivel_apos_investimentos": disponivel_apos_investimentos,
            "percentual_comprometido": comprometimento,
            "percentual_investimento_receita": percentual_investimento_receita,
            "total_lancamentos": total_lancamentos,
            "qtd_receitas": qtd_receitas,
            "qtd_despesas": qtd_despesas,
            "qtd_investimentos": qtd_investimentos,
            "qtd_a_classificar": qtd_a_classificar,
            "maior_categoria": maior_categoria,
            "maior_categoria_valor": maior_categoria_valor,
        },
        "resumo_formatado": {
            "receitas": analise.get("total_receitas_fmt", ""),
            "despesas": analise.get("total_despesas_fmt", ""),
            "investimentos": analise.get("total_investimentos_fmt", ""),
            "saldo": analise.get("saldo_fmt", ""),
            "disponivel_apos_investimentos": analise.get(
                "disponivel_apos_investimentos_fmt", ""
            ),
            "percentual_comprometido": analise.get("comprometimento_fmt", ""),
            "percentual_investimento_receita": analise.get(
                "percentual_investimento_receita_fmt", ""
            ),
            "maior_categoria_valor": analise.get("maior_categoria_valor_fmt", ""),
        },
        "cards": [
            {
                "titulo": "Receitas",
                "valor": total_receitas,
                "valor_fmt": analise.get("total_receitas_fmt", ""),
                "tipo": "receita",
                "icone": "arrow_down",
                "descricao": f"{qtd_receitas} lançamento(s)",
            },
            {
                "titulo": "Despesas",
                "valor": total_despesas,
                "valor_fmt": analise.get("total_despesas_fmt", ""),
                "tipo": "despesa",
                "icone": "arrow_up",
                "descricao": f"{qtd_despesas} lançamento(s)",
            },
            {
                "titulo": "Saldo",
                "valor": saldo,
                "valor_fmt": analise.get("saldo_fmt", ""),
                "tipo": "saldo",
                "icone": "wallet",
                "descricao": "Receitas menos despesas",
            },
            {
                "titulo": "Investimentos",
                "valor": total_investimentos,
                "valor_fmt": analise.get("total_investimentos_fmt", ""),
                "tipo": "investimento",
                "icone": "trending_up",
                "descricao": f"{qtd_investimentos} lançamento(s)",
            },
            {
                "titulo": "Comprometido",
                "valor": comprometimento,
                "valor_fmt": analise.get("comprometimento_fmt", ""),
                "sufixo": "%",
                "tipo": "percentual",
                "icone": "pie_chart",
                "descricao": "Despesas sobre receitas",
            },
            {
                "titulo": "Maior categoria",
                "valor": maior_categoria_valor,
                "valor_fmt": analise.get("maior_categoria_valor_fmt", ""),
                "tipo": "categoria",
                "icone": "tag",
                "descricao": str(maior_categoria),
            },
            {
                "titulo": "A classificar",
                "valor": qtd_a_classificar,
                "valor_fmt": str(qtd_a_classificar),
                "tipo": "alerta",
                "icone": "alert_triangle",
                "descricao": "Lançamentos pendentes de classificação",
            },
            {
                "titulo": "Total de lançamentos",
                "valor": total_lancamentos,
                "valor_fmt": str(total_lancamentos),
                "tipo": "contador",
                "icone": "list",
                "descricao": "Movimentações no período",
            },
        ],
        "origem": "painel_gerencial_web_real_resumido",
    }