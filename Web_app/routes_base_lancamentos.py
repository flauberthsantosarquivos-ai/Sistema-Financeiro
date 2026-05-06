from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.dashboard_base import (
    filtrar_por_periodo,
    formatar_moeda,
    ler_base_lancamentos,
    para_float,
)
from core.financeiro.lancamentos_google import (
    CABECALHOS_BASE,
    abrir_planilha_e_base,
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


def normalizar(valor: str | None) -> str:
    return str(valor or "").strip().upper()


def formatar_numero_brasil(valor: float) -> str:
    if not valor:
        return ""
    return f"{valor:.2f}".replace(".", ",")


def preparar_linhas(registros: list[dict]) -> list[dict]:
    linhas = []

    for item in registros:
        valor_previsto = abs(para_float(item.get("VALOR_PREVISTO")))
        valor_realizado = abs(para_float(item.get("VALOR_REALIZADO")))

        linhas.append(
            {
                "id": item.get("ID", ""),
                "data": item.get("DATA", ""),
                "mes": item.get("MES", ""),
                "ano": item.get("ANO", ""),
                "tipo": item.get("TIPO", ""),
                "categoria": item.get("CATEGORIA", ""),
                "subcategoria": item.get("SUBCATEGORIA", ""),
                "descricao": item.get("DESCRICAO", ""),
                "valor_previsto": valor_previsto,
                "valor_realizado": valor_realizado,
                "valor_previsto_raw": formatar_numero_brasil(valor_previsto),
                "valor_realizado_raw": formatar_numero_brasil(valor_realizado),
                "valor_previsto_fmt": formatar_moeda(valor_previsto),
                "valor_realizado_fmt": formatar_moeda(valor_realizado),
                "situacao": item.get("SITUACAO", ""),
                "forma_pagamento": item.get("FORMA_PAGAMENTO", ""),
                "conta": item.get("CONTA", ""),
                "origem": item.get("ORIGEM", ""),
                "observacao": item.get("OBSERVACAO", ""),
                "criado_em": item.get("CRIADO_EM", ""),
            }
        )

    return linhas


def calcular_totais_financeiros(linhas: list[dict]) -> dict:
    total_receitas = 0.0
    total_despesas = 0.0

    for item in linhas:
        tipo = str(item.get("tipo", "")).strip().upper()

        valor_realizado = float(item.get("valor_realizado", 0) or 0)
        valor_previsto = float(item.get("valor_previsto", 0) or 0)

        valor_base = valor_realizado if valor_realizado > 0 else valor_previsto

        if tipo == "RECEITA":
            total_receitas += valor_base
        elif tipo == "DESPESA":
            total_despesas += valor_base

    saldo = total_receitas - total_despesas

    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "saldo": saldo,
        "total_receitas_fmt": formatar_moeda(total_receitas),
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "saldo_fmt": formatar_moeda(saldo),
        "saldo_valor": saldo,
    }


def aplicar_filtros_avancados(
    registros: list[dict],
    tipo: str,
    situacao: str,
    origem: str,
    categoria: str,
    texto: str,
) -> list[dict]:
    tipo = normalizar(tipo)
    situacao = normalizar(situacao)
    origem = normalizar(origem)
    categoria = normalizar(categoria)
    texto = normalizar(texto)

    filtrados = []

    for item in registros:
        item_tipo = normalizar(item.get("TIPO"))
        item_situacao = normalizar(item.get("SITUACAO"))
        item_origem = normalizar(item.get("ORIGEM"))
        item_categoria = normalizar(item.get("CATEGORIA"))

        texto_busca = " ".join(
            [
                normalizar(item.get("DATA")),
                normalizar(item.get("MES")),
                normalizar(item.get("ANO")),
                normalizar(item.get("TIPO")),
                normalizar(item.get("CATEGORIA")),
                normalizar(item.get("SUBCATEGORIA")),
                normalizar(item.get("DESCRICAO")),
                normalizar(item.get("SITUACAO")),
                normalizar(item.get("FORMA_PAGAMENTO")),
                normalizar(item.get("CONTA")),
                normalizar(item.get("ORIGEM")),
                normalizar(item.get("OBSERVACAO")),
            ]
        )

        if tipo and item_tipo != tipo:
            continue

        if situacao and item_situacao != situacao:
            continue

        if origem and item_origem != origem:
            continue

        if categoria and item_categoria != categoria:
            continue

        if texto and texto not in texto_busca:
            continue

        filtrados.append(item)

    return filtrados


def montar_opcoes_unicas(registros: list[dict], campo: str) -> list[str]:
    valores = set()

    for item in registros:
        valor = str(item.get(campo, "")).strip()

        if valor:
            valores.add(valor)

    return sorted(valores)


def montar_url_retorno(return_url: str, chave: str, mensagem: str) -> str:
    """
    Mantém o usuário na mesma tela/filtro depois da edição rápida.
    Também evita redirecionamento para fora da área da BASE_LANCAMENTOS.
    """
    if not return_url or not return_url.startswith("/financeiro/base-lancamentos"):
        return_url = "/financeiro/base-lancamentos"

    separador = "&" if "?" in return_url else "?"
    mensagem_segura = quote(str(mensagem or ""))

    return f"{return_url}{separador}{chave}={mensagem_segura}"


def localizar_lancamento_por_id(lancamento_id: str):
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    if not link_planilha:
        raise ValueError("Nenhuma planilha vinculada foi encontrada.")

    _, aba = abrir_planilha_e_base(link_planilha)

    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        raise ValueError("BASE_LANCAMENTOS está vazia.")

    for indice_linha, linha in enumerate(valores[1:], start=2):
        linha_completa = linha + [""] * (len(CABECALHOS_BASE) - len(linha))

        registro = {
            cabecalho: linha_completa[indice]
            for indice, cabecalho in enumerate(CABECALHOS_BASE)
        }

        if str(registro.get("ID", "")).strip() == lancamento_id:
            return aba, indice_linha, registro

    raise ValueError("Lançamento não encontrado na BASE_LANCAMENTOS.")


def localizar_linhas_por_ids(ids_lancamentos: list[str]) -> tuple[object, list[int]]:
    config = obter_configuracao_sistema()
    link_planilha = config.get("planilha_google", "")

    if not link_planilha:
        raise ValueError("Nenhuma planilha vinculada foi encontrada.")

    _, aba = abrir_planilha_e_base(link_planilha)

    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        raise ValueError("BASE_LANCAMENTOS está vazia.")

    ids_procurados = {str(item).strip() for item in ids_lancamentos if str(item).strip()}

    if not ids_procurados:
        raise ValueError("Nenhum lançamento foi selecionado para exclusão.")

    linhas_encontradas = []

    for indice_linha, linha in enumerate(valores[1:], start=2):
        linha_completa = linha + [""] * (len(CABECALHOS_BASE) - len(linha))

        registro = {
            cabecalho: linha_completa[indice]
            for indice, cabecalho in enumerate(CABECALHOS_BASE)
        }

        lancamento_id = str(registro.get("ID", "")).strip()

        if lancamento_id in ids_procurados:
            linhas_encontradas.append(indice_linha)

    if not linhas_encontradas:
        raise ValueError("Nenhum dos lançamentos selecionados foi encontrado na BASE_LANCAMENTOS.")

    return aba, linhas_encontradas


@router.get("/financeiro/base-lancamentos", response_class=HTMLResponse)
async def base_lancamentos_get(
    request: Request,
    periodo_tipo: str = Query("todos"),
    mes_unico: str = Query("MAI"),
    mes_inicio: str = Query("JAN"),
    mes_fim: str = Query("DEZ"),
    ano: str | None = Query(None),
    tipo: str = Query(""),
    situacao: str = Query(""),
    origem: str = Query(""),
    categoria: str = Query(""),
    texto: str = Query(""),
    mensagem: str | None = Query(None),
    erro: str | None = Query(None),
):
    config = obter_configuracao_sistema()
    ano_final = ano or str(config.get("ano_base", date.today().year))

    filtros = {
        "periodo_tipo": periodo_tipo,
        "mes_unico": mes_unico,
        "mes_inicio": mes_inicio,
        "mes_fim": mes_fim,
        "ano": ano_final,
        "tipo": tipo,
        "situacao": situacao,
        "origem": origem,
        "categoria": categoria,
        "texto": texto,
    }

    try:
        registros = ler_base_lancamentos()

        registros_periodo = filtrar_por_periodo(
            registros=registros,
            periodo_tipo=periodo_tipo,
            mes_unico=mes_unico,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            ano=ano_final,
        )

        registros_filtrados = aplicar_filtros_avancados(
            registros=registros_periodo,
            tipo=tipo,
            situacao=situacao,
            origem=origem,
            categoria=categoria,
            texto=texto,
        )

        linhas = preparar_linhas(registros_filtrados)
        totais = calcular_totais_financeiros(linhas)

        return templates.TemplateResponse(
            request=request,
            name="base_lancamentos.html",
            context={
                "erro": erro,
                "mensagem": mensagem,
                "linhas": linhas,
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "tipos_opcoes": montar_opcoes_unicas(registros, "TIPO"),
                "situacoes_opcoes": montar_opcoes_unicas(registros, "SITUACAO"),
                "origens_opcoes": montar_opcoes_unicas(registros, "ORIGEM"),
                "categorias_opcoes": montar_opcoes_unicas(registros, "CATEGORIA"),
                "total_registros": len(linhas),
                "total_receitas_fmt": totais["total_receitas_fmt"],
                "total_despesas_fmt": totais["total_despesas_fmt"],
                "saldo_fmt": totais["saldo_fmt"],
                "saldo_valor": totais["saldo_valor"],
                "planilha_google": config.get("planilha_google", ""),
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="base_lancamentos.html",
            context={
                "erro": f"Erro ao carregar BASE_LANCAMENTOS: {e}",
                "mensagem": None,
                "linhas": [],
                "filtros": filtros,
                "meses_opcoes": MESES_OPCOES,
                "tipos_opcoes": [],
                "situacoes_opcoes": [],
                "origens_opcoes": [],
                "categorias_opcoes": [],
                "total_registros": 0,
                "total_receitas_fmt": formatar_moeda(0),
                "total_despesas_fmt": formatar_moeda(0),
                "saldo_fmt": formatar_moeda(0),
                "saldo_valor": 0,
                "planilha_google": config.get("planilha_google", ""),
            },
        )


@router.get("/financeiro/base-lancamentos/editar/{lancamento_id}", response_class=HTMLResponse)
async def editar_lancamento_get(request: Request, lancamento_id: str):
    try:
        _, _, registro = localizar_lancamento_por_id(lancamento_id)

        return templates.TemplateResponse(
            request=request,
            name="base_lancamento_editar.html",
            context={
                "erro": None,
                "mensagem": None,
                "lancamento": registro,
                "meses_opcoes": MESES_OPCOES,
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="base_lancamento_editar.html",
            context={
                "erro": f"Erro ao abrir lançamento para edição: {e}",
                "mensagem": None,
                "lancamento": None,
                "meses_opcoes": MESES_OPCOES,
            },
        )


@router.post("/financeiro/base-lancamentos/editar/{lancamento_id}", response_class=HTMLResponse)
async def editar_lancamento_post(
    request: Request,
    lancamento_id: str,
    data: str = Form(""),
    mes: str = Form(""),
    ano: str = Form(""),
    tipo: str = Form(""),
    categoria: str = Form(""),
    subcategoria: str = Form(""),
    descricao: str = Form(""),
    valor_previsto: str = Form(""),
    valor_realizado: str = Form(""),
    situacao: str = Form(""),
    forma_pagamento: str = Form(""),
    conta: str = Form(""),
    origem: str = Form(""),
    observacao: str = Form(""),
):
    try:
        aba, indice_linha, registro_antigo = localizar_lancamento_por_id(lancamento_id)

        nova_linha = [
            lancamento_id,
            data,
            mes,
            ano,
            tipo,
            categoria,
            subcategoria,
            descricao,
            valor_previsto,
            valor_realizado,
            situacao,
            forma_pagamento,
            conta,
            origem,
            observacao,
            registro_antigo.get("CRIADO_EM", ""),
        ]

        aba.update(
            f"A{indice_linha}:P{indice_linha}",
            [nova_linha],
            value_input_option="USER_ENTERED",
        )

        registro_atualizado = {
            "ID": lancamento_id,
            "DATA": data,
            "MES": mes,
            "ANO": ano,
            "TIPO": tipo,
            "CATEGORIA": categoria,
            "SUBCATEGORIA": subcategoria,
            "DESCRICAO": descricao,
            "VALOR_PREVISTO": valor_previsto,
            "VALOR_REALIZADO": valor_realizado,
            "SITUACAO": situacao,
            "FORMA_PAGAMENTO": forma_pagamento,
            "CONTA": conta,
            "ORIGEM": origem,
            "OBSERVACAO": observacao,
            "CRIADO_EM": registro_antigo.get("CRIADO_EM", ""),
        }

        return templates.TemplateResponse(
            request=request,
            name="base_lancamento_editar.html",
            context={
                "erro": None,
                "mensagem": "Lançamento atualizado com sucesso.",
                "lancamento": registro_atualizado,
                "meses_opcoes": MESES_OPCOES,
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="base_lancamento_editar.html",
            context={
                "erro": f"Erro ao salvar edição: {e}",
                "mensagem": None,
                "lancamento": None,
                "meses_opcoes": MESES_OPCOES,
            },
        )


@router.post("/financeiro/base-lancamentos/editar-rapido/{lancamento_id}")
async def editar_lancamento_rapido_post(
    lancamento_id: str,
    data: str = Form(""),
    mes: str = Form(""),
    ano: str = Form(""),
    tipo: str = Form(""),
    categoria: str = Form(""),
    subcategoria: str = Form(""),
    descricao: str = Form(""),
    valor_previsto: str = Form(""),
    valor_realizado: str = Form(""),
    situacao: str = Form(""),
    forma_pagamento: str = Form(""),
    conta: str = Form(""),
    origem: str = Form(""),
    observacao: str = Form(""),
    return_url: str = Form("/financeiro/base-lancamentos"),
):
    try:
        aba, indice_linha, registro_antigo = localizar_lancamento_por_id(lancamento_id)

        nova_linha = [
            lancamento_id,
            data,
            mes,
            ano,
            tipo,
            categoria,
            subcategoria,
            descricao,
            valor_previsto,
            valor_realizado,
            situacao,
            forma_pagamento,
            conta,
            origem,
            observacao,
            registro_antigo.get("CRIADO_EM", ""),
        ]

        aba.update(
            f"A{indice_linha}:P{indice_linha}",
            [nova_linha],
            value_input_option="USER_ENTERED",
        )

        return RedirectResponse(
            url=montar_url_retorno(
                return_url=return_url,
                chave="mensagem",
                mensagem="Lançamento atualizado com sucesso.",
            ),
            status_code=303,
        )

    except Exception as e:
        return RedirectResponse(
            url=montar_url_retorno(
                return_url=return_url,
                chave="erro",
                mensagem=f"Erro ao atualizar lançamento: {e}",
            ),
            status_code=303,
        )


@router.post("/financeiro/base-lancamentos/excluir/{lancamento_id}")
async def excluir_lancamento_post(
    lancamento_id: str,
    confirmar_exclusao: str = Form("NAO"),
):
    try:
        if confirmar_exclusao != "SIM":
            return RedirectResponse(
                url="/financeiro/base-lancamentos?erro=Confirmação de exclusão não marcada.",
                status_code=303,
            )

        aba, indice_linha, _ = localizar_lancamento_por_id(lancamento_id)

        aba.delete_rows(indice_linha)

        return RedirectResponse(
            url="/financeiro/base-lancamentos?mensagem=Lançamento excluído com sucesso.",
            status_code=303,
        )

    except Exception as e:
        return RedirectResponse(
            url=f"/financeiro/base-lancamentos?erro=Erro ao excluir lançamento: {e}",
            status_code=303,
        )


@router.post("/financeiro/base-lancamentos/excluir-selecionados")
async def excluir_lancamentos_selecionados_post(
    lancamentos_ids: list[str] = Form(default=[]),
):
    try:
        if not lancamentos_ids:
            return RedirectResponse(
                url="/financeiro/base-lancamentos?erro=Nenhum lançamento foi selecionado para exclusão.",
                status_code=303,
            )

        aba, linhas_para_excluir = localizar_linhas_por_ids(lancamentos_ids)

        for indice_linha in sorted(linhas_para_excluir, reverse=True):
            aba.delete_rows(indice_linha)

        quantidade = len(linhas_para_excluir)

        return RedirectResponse(
            url=f"/financeiro/base-lancamentos?mensagem={quantidade} lançamento(s) excluído(s) com sucesso.",
            status_code=303,
        )

    except Exception as e:
        return RedirectResponse(
            url=f"/financeiro/base-lancamentos?erro=Erro ao excluir lançamentos selecionados: {e}",
            status_code=303,
        )