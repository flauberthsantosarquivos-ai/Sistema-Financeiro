from __future__ import annotations

from mobile_api.financeiro_adapter import montar_referencia, obter_periodo_padrao

from core.financeiro.patrimonio_google import montar_resumo_patrimonio


def _mes_sigla(mes: int) -> str:
    meses = {
        1: "JAN",
        2: "FEV",
        3: "MAR",
        4: "ABR",
        5: "MAI",
        6: "JUN",
        7: "JUL",
        8: "AGO",
        9: "SET",
        10: "OUT",
        11: "NOV",
        12: "DEZ",
    }
    return meses.get(int(mes or 0), "")


def _montar_itens_mobile(ativos: list[dict]) -> list[dict]:
    itens = []

    for ativo in ativos:
        nome = str(ativo.get("nome", "") or "").strip()
        valor = float(ativo.get("fim", 0) or 0)

        if not nome:
            continue

        subdivisoes = []
        for subdivisao in ativo.get("subdivisoes", []) or []:
            subdivisoes.append(
                {
                    "nome": str(subdivisao.get("nome", "") or "").strip(),
                    "valor": float(subdivisao.get("fim", 0) or 0),
                    "valor_fmt": str(subdivisao.get("fim_fmt", "") or ""),
                }
            )

        itens.append(
            {
                "grupo": nome,
                "descricao": (
                    f"{len(subdivisoes)} subdivisão(ões)"
                    if ativo.get("tem_subdivisoes")
                    else "Saldo consolidado"
                ),
                "valor": valor,
                "valor_fmt": str(ativo.get("fim_fmt", "") or ""),
                "participacao": float(ativo.get("participacao", 0) or 0),
                "participacao_fmt": str(ativo.get("participacao_fmt", "") or ""),
                "subdivisoes": subdivisoes,
            }
        )

    return itens


def obter_patrimonio_mobile(
    ano: int | None = None,
    mes: int | None = None,
) -> dict:
    """
    Retorna o patrimônio real salvo na aba PATRIMONIO_FINANCEIRO.

    Quando não houver fechamento para o mês solicitado, usa o último
    patrimônio disponível, para o celular sempre mostrar o total atual.
    """

    ano_solicitado, mes_solicitado = obter_periodo_padrao(ano, mes)
    mes_sigla_solicitada = _mes_sigla(mes_solicitado)

    resumo = montar_resumo_patrimonio(
        ano_resumo=str(ano_solicitado),
        mes_resumo=mes_sigla_solicitada,
    )

    if not resumo.get("tem_dados_mes_resumo"):
        resumo = montar_resumo_patrimonio()

    ano_referencia = str(resumo.get("ano_resumo", "") or "")
    mes_referencia = str(resumo.get("mes_resumo", "") or "")
    possui_dados = bool(resumo.get("tem_dados_mes_resumo"))

    referencia = (
        f"{ano_referencia}-{mes_referencia}"
        if ano_referencia and mes_referencia
        else montar_referencia(ano_solicitado, mes_solicitado)
    )

    total_atual = float(resumo.get("total_atual", 0) or 0)
    variacao = float(resumo.get("variacao", 0) or 0)
    percentual_variacao = float(resumo.get("percentual_variacao", 0) or 0)

    return {
        "mes": referencia,
        "periodo": {
            "ano": ano_referencia or ano_solicitado,
            "mes": mes_referencia or mes_sigla_solicitada,
            "referencia": referencia,
            "solicitado_ano": ano_solicitado,
            "solicitado_mes": mes_solicitado,
        },
        "tem_dados": possui_dados,
        "patrimonio_total": total_atual,
        "patrimonio_total_fmt": str(resumo.get("total_atual_fmt", "") or ""),
        "variacao_mes": variacao,
        "variacao_mes_fmt": str(resumo.get("variacao_fmt", "") or ""),
        "percentual_variacao": percentual_variacao,
        "percentual_variacao_fmt": str(
            resumo.get("percentual_variacao_fmt", "") or ""
        ),
        "data_inicio": str((resumo.get("ultimo") or {}).get("DATA_INICIO", "") or ""),
        "data_fim": str((resumo.get("ultimo") or {}).get("DATA_FIM", "") or ""),
        "maior_ativo": (
            {
                "nome": str((resumo.get("maior_ativo") or {}).get("nome", "") or ""),
                "valor": float((resumo.get("maior_ativo") or {}).get("fim", 0) or 0),
                "valor_fmt": str(
                    (resumo.get("maior_ativo") or {}).get("fim_fmt", "") or ""
                ),
            }
            if resumo.get("maior_ativo")
            else None
        ),
        "itens": _montar_itens_mobile(resumo.get("ativos", []) or []),
        "origem": "patrimonio_financeiro_real",
    }
