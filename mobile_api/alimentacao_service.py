from __future__ import annotations

from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao
from core.financeiro.alimentacao_google import montar_resumo_alimentacao


def obter_alimentacao_mobile(
    ano: int | None = None,
    mes: int | None = None,
) -> dict:
    """Retorna uma visão somente de leitura do módulo Alimentação para o app."""
    ano, mes = obter_periodo_padrao(ano, mes)
    ano_texto = str(ano)
    mes_texto = str(mes).zfill(2)

    resumo = montar_resumo_alimentacao(ano_texto, mes_texto)
    contas = resumo.get("contas", []) or []
    movimentacoes = resumo.get("movimentacoes", []) or []

    ultimas_movimentacoes = []
    for item in movimentacoes[:30]:
        tipo = str(item.get("TIPO", "")).strip().upper()
        ultimas_movimentacoes.append(
            {
                "data": str(item.get("DATA", "")).strip(),
                "conta": str(item.get("CONTA", "")).strip().upper(),
                "tipo": tipo,
                "descricao": str(item.get("DESCRICAO", "")).strip(),
                "valor": float(item.get("VALOR_NUM", 0) or 0),
                "valor_fmt": str(item.get("VALOR_FMT", "R$ 0,00")),
            }
        )

    return {
        "periodo": {
            "ano": ano,
            "mes": mes,
            "referencia": montar_referencia(ano, mes),
        },
        "resumo": {
            "total_saldo": float(resumo.get("total_saldo", 0) or 0),
            "total_saldo_fmt": str(resumo.get("total_saldo_fmt", "R$ 0,00")),
            "total_entradas": float(resumo.get("total_entradas", 0) or 0),
            "total_entradas_fmt": str(resumo.get("total_entradas_fmt", "R$ 0,00")),
            "total_saidas": float(resumo.get("total_saidas", 0) or 0),
            "total_saidas_fmt": str(resumo.get("total_saidas_fmt", "R$ 0,00")),
            "qtd_movimentacoes": int(resumo.get("qtd_movimentacoes", 0) or 0),
        },
        "contas": contas,
        "movimentacoes": ultimas_movimentacoes,
        "origem": "alimentacao_web_real_resumido",
    }
