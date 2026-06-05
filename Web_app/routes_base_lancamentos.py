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
from core.financeiro.categorias_google import (
    obter_estrutura_categorias,
    validar_categoria_subcategoria,
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


def mes_corrente_sigla() -> str:
    """
    Retorna a sigla do mês corrente no mesmo padrão usado na BASE_LANCAMENTOS.

    Exemplo:
    Janeiro -> JAN
    Fevereiro -> FEV
    Maio -> MAI
    """
    hoje = date.today()
    return MESES_OPCOES[hoje.month - 1][0]


def normalizar(valor: str | None) -> str:
    return str(valor or "").strip().upper()


def coluna_para_letra(indice: int) -> str:
    """
    Converte índice 1-based para letra de coluna do Google Sheets.
    Exemplo: 1 -> A, 16 -> P, 17 -> Q.
    """

    letras = ""

    while indice > 0:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras

    return letras


def range_linha_base(indice_linha: int) -> str:
    return f"A{indice_linha}:{coluna_para_letra(len(CABECALHOS_BASE))}{indice_linha}"


def montar_return_url(request: Request | None = None, return_url: str | None = None) -> str:
    """
    Mantém o usuário na mesma tela/filtro após editar ou excluir.
    Só aceita retorno interno da própria Base para evitar redirecionamento externo.
    """

    if return_url:
        retorno = str(return_url).strip()

        if retorno.startswith("/financeiro/base-lancamentos"):
            return retorno

    if request:
        query = str(request.url.query or "").strip()

        if query:
            return f"{request.url.path}?{query}"

        return str(request.url.path)

    return "/financeiro/base-lancamentos"


def redirecionar_base_com_msg(
    request: Request | None = None,
    return_url: str | None = None,
    mensagem: str | None = None,
    erro: str | None = None,
) -> RedirectResponse:
    destino = montar_return_url(request=request, return_url=return_url)
    separador = "&" if "?" in destino else "?"

    if mensagem:
        destino = f"{destino}{separador}mensagem={quote(mensagem)}"
        separador = "&"

    if erro:
        destino = f"{destino}{separador}erro={quote(erro)}"

    return RedirectResponse(
        url=destino,
        status_code=303,
    )


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
                "data_banco": item.get("DATA_BANCO", ""),
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
                normalizar(item.get("DATA_BANCO")),
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


def obter_estrutura_categorias_segura() -> dict:
    try:
        return obter_estrutura_categorias(incluir_inativas=False)
    except Exception:
        return {}


def mesclar_opcoes(*listas: list[str]) -> list[str]:
    valores = set()

    for lista in listas:
        for item in lista or []:
            texto = str(item or "").strip().upper()
            if texto:
                valores.add(texto)

    return sorted(valores)


def categorias_oficiais_lista(estrutura: dict) -> list[str]:
    categorias = set()

    for categorias_por_tipo in estrutura.values():
        for categoria in categorias_por_tipo.keys():
            texto = str(categoria or "").strip().upper()
            if texto:
                categorias.add(texto)

    return sorted(categorias)


def validar_categoria_base(tipo: str, categoria: str, subcategoria: str) -> tuple[str, str, str]:
    if not str(tipo or "").strip():
        raise ValueError("Informe o tipo do lançamento.")

    if not str(categoria or "").strip():
        raise ValueError("Informe uma categoria cadastrada na aba CATEGORIAS.")

    return validar_categoria_subcategoria(
        tipo=tipo,
        categoria=categoria,
        subcategoria=subcategoria,
    )


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
    periodo_tipo: str | None = Query(None),
    mes_unico: str | None = Query(None),
    mes_inicio: str | None = Query(None),
    mes_fim: str | None = Query(None),
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

    # Ao abrir /financeiro/base-lancamentos sem filtros de período,
    # a tela deve apresentar o mês corrente como padrão.
    hoje = date.today()
    ano_final = ano or str(hoje.year)

    if not periodo_tipo:
        periodo_tipo = "mes_unico"

    if not mes_unico:
        mes_unico = mes_corrente_sigla()

    if not mes_inicio:
        mes_inicio = "JAN"

    if not mes_fim:
        mes_fim = "DEZ"

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
        categorias_estrutura = obter_estrutura_categorias_segura()

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
                "tipos_opcoes": mesclar_opcoes(list(categorias_estrutura.keys()), montar_opcoes_unicas(registros, "TIPO")),
                "situacoes_opcoes": montar_opcoes_unicas(registros, "SITUACAO"),
                "origens_opcoes": montar_opcoes_unicas(registros, "ORIGEM"),
                "categorias_opcoes": mesclar_opcoes(categorias_oficiais_lista(categorias_estrutura), montar_opcoes_unicas(registros, "CATEGORIA")),
                "categorias_estrutura": categorias_estrutura,
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
                "categorias_estrutura": {},
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
                "categorias_estrutura": obter_estrutura_categorias_segura(),
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
                "categorias_estrutura": obter_estrutura_categorias_segura(),
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
        tipo, categoria, subcategoria = validar_categoria_base(tipo, categoria, subcategoria)

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
            registro_antigo.get("DATA_BANCO", ""),
        ]

        aba.update(
            range_linha_base(indice_linha),
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
            "DATA_BANCO": registro_antigo.get("DATA_BANCO", ""),
        }

        return templates.TemplateResponse(
            request=request,
            name="base_lancamento_editar.html",
            context={
                "erro": None,
                "mensagem": "Lançamento atualizado com sucesso.",
                "lancamento": registro_atualizado,
                "meses_opcoes": MESES_OPCOES,
                "categorias_estrutura": obter_estrutura_categorias_segura(),
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
                "categorias_estrutura": obter_estrutura_categorias_segura(),
            },
        )


@router.post("/financeiro/base-lancamentos/editar-rapido/{lancamento_id}")
async def editar_lancamento_rapido_post(
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
    return_url: str = Form(""),
):
    try:
        aba, indice_linha, registro_antigo = localizar_lancamento_por_id(lancamento_id)
        tipo, categoria, subcategoria = validar_categoria_base(tipo, categoria, subcategoria)

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
            registro_antigo.get("DATA_BANCO", ""),
        ]

        aba.update(
            range_linha_base(indice_linha),
            [nova_linha],
            value_input_option="USER_ENTERED",
        )

        return redirecionar_base_com_msg(
            return_url=return_url,
            mensagem="Lançamento atualizado com sucesso.",
        )

    except Exception as e:
        return redirecionar_base_com_msg(
            return_url=return_url,
            erro=f"Erro ao atualizar lançamento: {e}",
        )


@router.post("/financeiro/base-lancamentos/excluir/{lancamento_id}")
async def excluir_lancamento_post(
    request: Request,
    lancamento_id: str,
    confirmar_exclusao: str = Form("NAO"),
    return_url: str = Form(""),
):
    try:
        if confirmar_exclusao != "SIM":
            return redirecionar_base_com_msg(
                request=request,
                return_url=return_url,
                erro="Confirmação de exclusão não marcada.",
            )

        aba, indice_linha, _ = localizar_lancamento_por_id(lancamento_id)

        aba.delete_rows(indice_linha)

        return redirecionar_base_com_msg(
            request=request,
            return_url=return_url,
            mensagem="Lançamento excluído com sucesso.",
        )

    except Exception as e:
        return redirecionar_base_com_msg(
            request=request,
            return_url=return_url,
            erro=f"Erro ao excluir lançamento: {e}",
        )


@router.post("/financeiro/base-lancamentos/excluir-selecionados")
async def excluir_lancamentos_selecionados_post(
    request: Request,
    lancamentos_ids: list[str] = Form(default=[]),
    return_url: str = Form(""),
):
    try:
        if not lancamentos_ids:
            return redirecionar_base_com_msg(
                request=request,
                return_url=return_url,
                erro="Nenhum lançamento foi selecionado para exclusão.",
            )

        aba, linhas_para_excluir = localizar_linhas_por_ids(lancamentos_ids)

        for indice_linha in sorted(linhas_para_excluir, reverse=True):
            aba.delete_rows(indice_linha)

        quantidade = len(linhas_para_excluir)

        return redirecionar_base_com_msg(
            request=request,
            return_url=return_url,
            mensagem=f"{quantidade} lançamento(s) excluído(s) com sucesso.",
        )

    except Exception as e:
        return redirecionar_base_com_msg(
            request=request,
            return_url=return_url,
            erro=f"Erro ao excluir lançamentos selecionados: {e}",
        )
