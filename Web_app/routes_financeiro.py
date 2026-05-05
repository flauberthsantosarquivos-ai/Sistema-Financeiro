from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import (
    filtrar_por_periodo,
    formatar_moeda,
    ler_base_lancamentos,
    para_float,
)


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


MESES_OPCOES = [
    ("JAN", "Janeiro"),
    ("FEV", "Fevereiro"),
    ("MAR", "Março"),
    ("ABR", "Abril"),
    ("MAI", "Maio"),
    ("JUN", "Junho"),
    ("JUL", "Julho"),
    ("AGO", "Agosto"),
    ("SET", "Setembro"),
    ("OUT", "Outubro"),
    ("NOV", "Novembro"),
    ("DEZ", "Dezembro"),
]


def normalizar(valor) -> str:
    return str(valor or "").strip().upper()


def valor_lancamento(item: dict) -> float:
    valor_realizado = abs(para_float(item.get("VALOR_REALIZADO")))
    valor_previsto = abs(para_float(item.get("VALOR_PREVISTO")))

    if valor_realizado > 0:
        return valor_realizado

    return valor_previsto


def preparar_analise(registros: list[dict]) -> dict:
    total_receitas = 0.0
    total_despesas = 0.0
    total_transferencias = 0.0

    qtd_receitas = 0
    qtd_despesas = 0
    qtd_transferencias = 0
    qtd_a_classificar = 0

    despesas_por_categoria = {}
    receitas_por_categoria = {}
    top_despesas = []

    for item in registros:
        tipo = normalizar(item.get("TIPO"))
        categoria = str(item.get("CATEGORIA", "")).strip() or "SEM CATEGORIA"
        subcategoria = str(item.get("SUBCATEGORIA", "")).strip() or "SEM SUBCATEGORIA"
        descricao = str(item.get("DESCRICAO", "")).strip()
        data = str(item.get("DATA", "")).strip()
        situacao = str(item.get("SITUACAO", "")).strip()

        valor = valor_lancamento(item)

        if valor <= 0:
            continue

        texto_classificacao = normalizar(
            " ".join(
                [
                    str(item.get("CATEGORIA", "")),
                    str(item.get("SUBCATEGORIA", "")),
                    str(item.get("DESCRICAO", "")),
                ]
            )
        )

        if "A CLASSIFICAR" in texto_classificacao:
            qtd_a_classificar += 1

        if tipo == "RECEITA":
            total_receitas += valor
            qtd_receitas += 1
            receitas_por_categoria[categoria] = receitas_por_categoria.get(categoria, 0.0) + valor

        elif tipo == "DESPESA":
            total_despesas += valor
            qtd_despesas += 1
            despesas_por_categoria[categoria] = despesas_por_categoria.get(categoria, 0.0) + valor

            top_despesas.append(
                {
                    "data": data,
                    "descricao": descricao,
                    "categoria": categoria,
                    "subcategoria": subcategoria,
                    "situacao": situacao,
                    "valor": valor,
                    "valor_fmt": formatar_moeda(valor),
                }
            )

        elif tipo in {"TRANSFERÊNCIA", "TRANSFERENCIA"}:
            total_transferencias += valor
            qtd_transferencias += 1

    saldo = total_receitas - total_despesas

    comprometimento = 0.0
    if total_receitas > 0:
        comprometimento = (total_despesas / total_receitas) * 100

    categorias_ordenadas = sorted(
        despesas_por_categoria.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    receitas_ordenadas = sorted(
        receitas_por_categoria.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_despesas = sorted(
        top_despesas,
        key=lambda item: item["valor"],
        reverse=True,
    )[:10]

    maior_categoria = categorias_ordenadas[0][0] if categorias_ordenadas else "Sem despesas"
    maior_categoria_valor = categorias_ordenadas[0][1] if categorias_ordenadas else 0.0

    diagnosticos = gerar_diagnostico(
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        saldo=saldo,
        comprometimento=comprometimento,
        qtd_a_classificar=qtd_a_classificar,
        maior_categoria=maior_categoria,
        maior_categoria_valor=maior_categoria_valor,
    )

    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "total_transferencias": total_transferencias,
        "saldo": saldo,
        "comprometimento": comprometimento,
        "qtd_receitas": qtd_receitas,
        "qtd_despesas": qtd_despesas,
        "qtd_transferencias": qtd_transferencias,
        "qtd_a_classificar": qtd_a_classificar,
        "total_lancamentos": len(registros),
        "total_receitas_fmt": formatar_moeda(total_receitas),
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "total_transferencias_fmt": formatar_moeda(total_transferencias),
        "saldo_fmt": formatar_moeda(saldo),
        "comprometimento_fmt": f"{comprometimento:.1f}".replace(".", ",") + "%",
        "maior_categoria": maior_categoria,
        "maior_categoria_valor_fmt": formatar_moeda(maior_categoria_valor),
        "despesas_por_categoria": [
            {
                "categoria": categoria,
                "valor": valor,
                "valor_fmt": formatar_moeda(valor),
                "percentual": (valor / total_despesas * 100) if total_despesas > 0 else 0,
                "percentual_fmt": f"{((valor / total_despesas * 100) if total_despesas > 0 else 0):.1f}".replace(".", ",") + "%",
            }
            for categoria, valor in categorias_ordenadas
        ],
        "receitas_por_categoria": [
            {
                "categoria": categoria,
                "valor": valor,
                "valor_fmt": formatar_moeda(valor),
            }
            for categoria, valor in receitas_ordenadas
        ],
        "top_despesas": top_despesas,
        "diagnosticos": diagnosticos,
        "chart_categorias_labels": [categoria for categoria, _ in categorias_ordenadas[:8]],
        "chart_categorias_valores": [round(valor, 2) for _, valor in categorias_ordenadas[:8]],
        "chart_resumo_labels": ["Receitas", "Despesas", "Transferências"],
        "chart_resumo_valores": [
            round(total_receitas, 2),
            round(total_despesas, 2),
            round(total_transferencias, 2),
        ],
    }


def gerar_diagnostico(
    total_receitas: float,
    total_despesas: float,
    saldo: float,
    comprometimento: float,
    qtd_a_classificar: int,
    maior_categoria: str,
    maior_categoria_valor: float,
) -> list[dict]:
    diagnosticos = []

    if total_receitas <= 0:
        diagnosticos.append(
            {
                "tipo": "alerta",
                "titulo": "Receita não identificada",
                "texto": "Não há receita registrada no período filtrado. Isso pode distorcer o cálculo de saldo e comprometimento.",
            }
        )
    else:
        if comprometimento <= 60:
            diagnosticos.append(
                {
                    "tipo": "positivo",
                    "titulo": "Comprometimento saudável",
                    "texto": f"As despesas representam {comprometimento:.1f}% da receita no período. O orçamento está com boa margem de controle.",
                }
            )
        elif comprometimento <= 80:
            diagnosticos.append(
                {
                    "tipo": "atencao",
                    "titulo": "Comprometimento moderado",
                    "texto": f"As despesas representam {comprometimento:.1f}% da receita. Ainda há saldo, mas vale revisar gastos variáveis.",
                }
            )
        else:
            diagnosticos.append(
                {
                    "tipo": "alerta",
                    "titulo": "Comprometimento elevado",
                    "texto": f"As despesas representam {comprometimento:.1f}% da receita. Recomenda-se revisar as maiores categorias de despesa.",
                }
            )

    if saldo >= 0:
        diagnosticos.append(
            {
                "tipo": "positivo",
                "titulo": "Saldo positivo",
                "texto": f"O saldo do período está positivo em {formatar_moeda(saldo)}.",
            }
        )
    else:
        diagnosticos.append(
            {
                "tipo": "alerta",
                "titulo": "Saldo negativo",
                "texto": f"O saldo do período está negativo em {formatar_moeda(abs(saldo))}. É necessário revisar despesas e lançamentos pendentes.",
            }
        )

    if qtd_a_classificar > 0:
        diagnosticos.append(
            {
                "tipo": "atencao",
                "titulo": "Lançamentos pendentes de classificação",
                "texto": f"Existem {qtd_a_classificar} lançamento(s) a classificar. Revise esses itens antes de fechar a análise do mês.",
            }
        )

    if maior_categoria and maior_categoria != "Sem despesas" and maior_categoria_valor > 0:
        diagnosticos.append(
            {
                "tipo": "info",
                "titulo": "Maior categoria de despesa",
                "texto": f"A maior categoria de despesa no período é {maior_categoria}, com {formatar_moeda(maior_categoria_valor)}.",
            }
        )

    return diagnosticos


@router.get("/financeiro", response_class=HTMLResponse)
async def financeiro_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="financeiro.html",
        context={},
    )


@router.get("/financeiro/analise", response_class=HTMLResponse)
async def analise_financeira_get(
    request: Request,
    periodo_tipo: str = Query("mes_unico"),
    mes_unico: str = Query("MAI"),
    mes_inicio: str = Query("JAN"),
    mes_fim: str = Query("DEZ"),
    ano: str | None = Query(None),
):
    config = obter_configuracao_sistema()
    ano_final = ano or str(config.get("ano_base", date.today().year))

    filtros = {
        "periodo_tipo": periodo_tipo,
        "mes_unico": mes_unico,
        "mes_inicio": mes_inicio,
        "mes_fim": mes_fim,
        "ano": ano_final,
    }

    try:
        registros = ler_base_lancamentos()

        registros_filtrados = filtrar_por_periodo(
            registros=registros,
            periodo_tipo=periodo_tipo,
            mes_unico=mes_unico,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            ano=ano_final,
        )

        analise = preparar_analise(registros_filtrados)

        return templates.TemplateResponse(
            request=request,
            name="analise_financeira.html",
            context={
                "erro": None,
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "analise": analise,
                "planilha_google": config.get("planilha_google", ""),
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="analise_financeira.html",
            context={
                "erro": f"Erro ao carregar análise financeira: {e}",
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "analise": preparar_analise([]),
                "planilha_google": config.get("planilha_google", ""),
            },
        )