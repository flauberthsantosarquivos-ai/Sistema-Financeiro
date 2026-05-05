from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.categorias import MESES, ORCAMENTO_PADRAO
from core.financeiro.lancamentos_google import (
    existe_planejamento_do_mes,
    salvar_lancamentos_em_lote_google,
)


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


def valor_para_float(valor: str | float | int | None) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        return 0.0


def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_data(ano: str, mes: str, dia: int) -> str:
    mapa_mes_numero = {
        "JAN": 1,
        "FEV": 2,
        "MAR": 3,
        "ABR": 4,
        "MAI": 5,
        "JUN": 6,
        "JUL": 7,
        "AGO": 8,
        "SET": 9,
        "OUT": 10,
        "NOV": 11,
        "DEZ": 12,
    }

    numero_mes = mapa_mes_numero.get(mes.upper(), date.today().month)
    ano_int = int(ano)

    try:
        return date(ano_int, numero_mes, int(dia)).isoformat()
    except ValueError:
        return date(ano_int, numero_mes, 1).isoformat()


def obter_mes_atual_sigla() -> str:
    hoje = date.today()

    return {
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
    }.get(hoje.month, "MAI")


def calcular_resumo_planejamento(receita_prevista: str):
    receita = valor_para_float(receita_prevista)

    total_reservado = 0.0
    total_previsto = 0.0
    total_geral = 0.0
    por_categoria = {}
    itens_formatados = []

    for item in ORCAMENTO_PADRAO:
        valor = valor_para_float(item.get("valor_padrao", "0"))

        situacao = item.get("situacao", "").upper()
        categoria = item.get("categoria", "OUTROS")

        if situacao == "RESERVADO":
            total_reservado += valor
        else:
            total_previsto += valor

        total_geral += valor
        por_categoria[categoria] = por_categoria.get(categoria, 0.0) + valor

        item_formatado = dict(item)
        item_formatado["valor_float"] = valor
        item_formatado["valor_fmt"] = formatar_moeda(valor)
        itens_formatados.append(item_formatado)

    saldo_estimado = receita - total_geral

    ranking_categorias = [
        {
            "categoria": categoria,
            "valor": valor,
            "valor_fmt": formatar_moeda(valor),
        }
        for categoria, valor in sorted(
            por_categoria.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    maior_categoria_valor = ranking_categorias[0]["valor"] if ranking_categorias else 1

    for item in ranking_categorias:
        if maior_categoria_valor > 0:
            item["percentual_visual"] = (item["valor"] / maior_categoria_valor) * 100
        else:
            item["percentual_visual"] = 0

    percentual_comprometimento = 0.0
    if receita > 0:
        percentual_comprometimento = (total_geral / receita) * 100

    return {
        "receita_prevista": receita,
        "receita_prevista_fmt": formatar_moeda(receita),
        "total_reservado": total_reservado,
        "total_reservado_fmt": formatar_moeda(total_reservado),
        "total_previsto": total_previsto,
        "total_previsto_fmt": formatar_moeda(total_previsto),
        "total_geral": total_geral,
        "total_geral_fmt": formatar_moeda(total_geral),
        "saldo_estimado": saldo_estimado,
        "saldo_estimado_fmt": formatar_moeda(saldo_estimado),
        "percentual_comprometimento": percentual_comprometimento,
        "percentual_comprometimento_fmt": f"{percentual_comprometimento:.2f}%",
        "ranking_categorias": ranking_categorias,
        "itens": itens_formatados,
    }


def montar_contexto(
    request: Request,
    mensagem: str | None = None,
    erro: str | None = None,
    mes_atual: str | None = None,
    ano_atual: int | None = None,
    receita_prevista: str | None = None,
):
    hoje = date.today()
    config = obter_configuracao_sistema()

    mes_final = mes_atual or obter_mes_atual_sigla()
    ano_final = ano_atual or int(config.get("ano_base", hoje.year))
    receita_final = receita_prevista or config.get("receita_padrao", "0,00")

    resumo = calcular_resumo_planejamento(receita_final)

    return {
        "request": request,
        "mensagem": mensagem,
        "erro": erro,
        "meses": MESES,
        "mes_atual": mes_final,
        "ano_atual": ano_final,
        "receita_prevista": receita_final,
        "link_planilha": config.get("planilha_google", ""),
        "orcamento_padrao": ORCAMENTO_PADRAO,
        "resumo": resumo,
    }


@router.get("/financeiro/planejamento", response_class=HTMLResponse)
async def planejamento_get(request: Request):
    config = obter_configuracao_sistema()

    return templates.TemplateResponse(
        request=request,
        name="planejamento.html",
        context=montar_contexto(
            request=request,
            mes_atual=obter_mes_atual_sigla(),
            ano_atual=int(config.get("ano_base", date.today().year)),
            receita_prevista=config.get("receita_padrao", "0,00"),
        ),
    )


@router.post("/financeiro/planejamento", response_class=HTMLResponse)
async def planejamento_post(
    request: Request,
    link_planilha: str = Form(...),
    mes: str = Form(...),
    ano: str = Form(...),
    receita_prevista: str = Form(...),
    substituir: str = Form("NAO"),
):
    try:
        config = obter_configuracao_sistema()
        link_planilha_final = config.get("planilha_google") or link_planilha

        if substituir != "SIM":
            if existe_planejamento_do_mes(
                link_planilha=link_planilha_final,
                mes=mes,
                ano=ano,
            ):
                return templates.TemplateResponse(
                    request=request,
                    name="planejamento.html",
                    context=montar_contexto(
                        request=request,
                        erro=(
                            f"Já existe planejamento gerado para {mes}/{ano}. "
                            "Para evitar duplicidade, marque a opção de confirmação antes de gerar novamente."
                        ),
                        mes_atual=mes,
                        ano_atual=int(ano),
                        receita_prevista=receita_prevista,
                    ),
                )

        lancamentos = []

        receita = valor_para_float(receita_prevista)

        if receita > 0:
            lancamentos.append(
                {
                    "data": montar_data(ano=ano, mes=mes, dia=1),
                    "mes": mes,
                    "ano": ano,
                    "tipo": "RECEITA",
                    "categoria": "SALÁRIO",
                    "subcategoria": "TRE",
                    "descricao": "Receita prevista do mês",
                    "valor_previsto": receita_prevista,
                    "valor_realizado": "",
                    "situacao": "PREVISTO",
                    "forma_pagamento": "CONTA",
                    "conta": config.get("conta_principal", "BANCO PRINCIPAL"),
                    "observacao": "Receita prevista incluída pelo planejamento mensal.",
                    "origem": "ORCAMENTO_PADRAO",
                }
            )

        for item in ORCAMENTO_PADRAO:
            valor = item.get("valor_padrao", "0,00")

            lancamentos.append(
                {
                    "data": montar_data(
                        ano=ano,
                        mes=mes,
                        dia=item.get("dia_base", 1),
                    ),
                    "mes": mes,
                    "ano": ano,
                    "tipo": item.get("tipo", "DESPESA"),
                    "categoria": item.get("categoria", ""),
                    "subcategoria": item.get("subcategoria", ""),
                    "descricao": item.get("descricao", ""),
                    "valor_previsto": valor,
                    "valor_realizado": valor if item.get("situacao") == "RESERVADO" else "",
                    "situacao": item.get("situacao", "PREVISTO"),
                    "forma_pagamento": item.get("forma_pagamento", ""),
                    "conta": item.get("conta", ""),
                    "observacao": item.get("observacao", ""),
                    "origem": "ORCAMENTO_PADRAO",
                }
            )

        url = salvar_lancamentos_em_lote_google(
            link_planilha=link_planilha_final,
            lancamentos=lancamentos,
        )

        return templates.TemplateResponse(
            request=request,
            name="planejamento.html",
            context=montar_contexto(
                request=request,
                mensagem=(
                    f"Planejamento de {mes}/{ano} gerado com sucesso. "
                    f"{len(lancamentos)} lançamentos foram criados na BASE_LANCAMENTOS. "
                    f"Planilha: {url}"
                ),
                mes_atual=mes,
                ano_atual=int(ano),
                receita_prevista=receita_prevista,
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="planejamento.html",
            context=montar_contexto(
                request=request,
                erro=f"Erro ao gerar planejamento mensal: {e}",
                mes_atual=mes,
                ano_atual=int(ano) if str(ano).isdigit() else date.today().year,
                receita_prevista=receita_prevista,
            ),
        )