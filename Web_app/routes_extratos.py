from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import obter_configuracao_sistema
from core.financeiro.categorias import (
    CONTAS,
    FORMAS_PAGAMENTO,
    MESES,
    SITUACOES,
)
from core.financeiro.categorias_google import (
    TIPOS_OFICIAIS,
    normalizar_tipo as normalizar_tipo_categoria,
    obter_estrutura_categorias,
)
from core.financeiro.dashboard_base import ler_base_lancamentos, para_float
from core.financeiro.lancamentos_google import salvar_lancamentos_em_lote_google
from core.financeiro.pagamentos_google import (
    conciliar_pagamentos_com_lancamentos_importados,
)
from core.financeiro.leitor_extrato import (
    carregar_previa_extrato,
    processar_extrato,
    salvar_previa_extrato,
)
from core.financeiro.regras_classificacao import aplicar_regras_cliente_no_resultado


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")

PASTA_UPLOAD_EXTRATOS = Path("uploads/extratos")
PASTA_UPLOAD_EXTRATOS.mkdir(parents=True, exist_ok=True)


@router.get("/financeiro/extratos", response_class=HTMLResponse)
async def extratos_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="extratos.html",
        context=montar_contexto_extratos(
            request=request,
            etapa="upload",
        ),
    )


@router.post("/financeiro/extratos/previsualizar", response_class=HTMLResponse)
async def extratos_previsualizar(
    request: Request,
    arquivo: UploadFile = File(...),
):
    nome = arquivo.filename or ""

    if not nome.lower().endswith((".csv", ".xlsx", ".xls")):
        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                erro="Formato ainda não suportado. Envie CSV, XLS ou XLSX.",
            ),
        )

    try:
        caminho_arquivo = PASTA_UPLOAD_EXTRATOS / f"{uuid4().hex}_{nome}"

        with caminho_arquivo.open("wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)

        resultado = processar_extrato(caminho_arquivo)

        config = obter_configuracao_sistema()
        link_planilha = config.get("planilha_google", "")

        if link_planilha:
            resultado = aplicar_regras_cliente_no_resultado(
                resultado=resultado,
                link_planilha=link_planilha,
            )

            # Reaproveita classificações já gravadas na BASE_LANCAMENTOS
            # e identifica movimentos que já existem antes de mostrar a prévia.
            resultado = aplicar_memoria_base_no_resultado(resultado)

        resultado = preparar_resultado_para_categorias_oficiais(resultado)
        resultado = atualizar_resumo_conferencia_resultado(resultado)

        temp_id = salvar_previa_extrato(resultado)

        qtd_regras = resultado.get("qtd_regras_cliente", 0)
        resumo_base = resultado.get("resumo_base", {}) or {}

        mensagem = (
            f"Extrato lido com sucesso. "
            f"{len(resultado.get('movimentacoes', []))} movimentações identificadas."
        )

        if qtd_regras:
            mensagem += f" {qtd_regras} regra(s) de classificação do cliente foram carregadas."

        qtd_reaproveitadas = int(resumo_base.get("classificacoes_reaproveitadas") or 0)
        qtd_existentes = int(resumo_base.get("ja_existentes_base") or 0)

        if qtd_reaproveitadas:
            mensagem += f" {qtd_reaproveitadas} classificação(ões) foram reaproveitadas da BASE_LANCAMENTOS."

        if qtd_existentes:
            mensagem += f" {qtd_existentes} lançamento(s) já existem na BASE e serão ignorados se forem confirmados."

        mensagem += " As categorias e subcategorias agora vêm da aba oficial CATEGORIAS."

        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="previa",
                mensagem=mensagem,
                temp_id=temp_id,
                resultado=resultado,
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                erro=f"Erro ao ler extrato: {e}",
            ),
        )


@router.post("/financeiro/extratos/importar", response_class=HTMLResponse)
async def extratos_importar(request: Request):
    form = await request.form()

    temp_id = str(form.get("temp_id", "")).strip()

    try:
        previa = carregar_previa_extrato(temp_id)
        movimentacoes = previa.get("movimentacoes", [])

        config = obter_configuracao_sistema()
        link_planilha = config.get("planilha_google", "")

        if not link_planilha:
            raise ValueError("Nenhuma planilha vinculada foi encontrada nas configurações.")

        # Lê a aba CATEGORIAS uma única vez nesta importação.
        # A validação de cada lançamento acontece em memória, evitando uma
        # leitura no Google Sheets por linha e o erro 429.
        estrutura_categorias_importacao = obter_estrutura_categorias()

        if not estrutura_categorias_importacao:
            raise ValueError(
                "Nenhuma categoria ativa foi encontrada na aba CATEGORIAS."
            )

        contexto_base = obter_contexto_base_lancamentos()
        chaves_existentes = set(contexto_base.get("chaves", set()))
        classificacoes_por_descricao_valor = contexto_base.get("classificacoes", {}) or {}

        lancamentos = []
        itens_importados = []
        itens_duplicados = []
        itens_saldos = []
        itens_desmarcados = []

        duplicados_ignorados = 0
        saldos_ignorados = 0
        desmarcados_usuario = 0
        classificacoes_reaproveitadas_importacao = 0
        total_movimentacoes = len(movimentacoes)

        for mov in movimentacoes:
            indice = str(mov.get("indice"))

            importar = form.get(f"importar_{indice}")

            if importar != "SIM":
                desmarcados_usuario += 1
                itens_desmarcados.append(resumir_movimentacao_importacao(mov, status="DESMARCADO"))
                continue

            valor = float(mov.get("valor", 0) or 0)
            valor_abs = abs(valor)

            tipo_form = str(form.get(f"tipo_{indice}", mov.get("tipo", ""))).strip()
            categoria_form = str(form.get(f"categoria_{indice}", mov.get("categoria", ""))).strip()
            subcategoria_form = str(form.get(f"subcategoria_{indice}", mov.get("subcategoria", ""))).strip()
            situacao = str(form.get(f"situacao_{indice}", mov.get("situacao", ""))).strip()
            forma_pagamento = str(form.get(f"forma_pagamento_{indice}", mov.get("forma_pagamento", ""))).strip()
            conta = str(form.get(f"conta_{indice}", mov.get("conta", ""))).strip()

            # Por padrão, a classificação pode ser reaproveitada nos próximos
            # extratos. A caixa da prévia permite desmarcar exceções, como
            # gastos de viagem.
            reaproveitar_classificacao = (
                "SIM" if form.get(f"reaproveitar_{indice}") == "SIM" else "NAO"
            )

            data = str(mov.get("data", "")).strip()
            data_banco = str(mov.get("data_banco", "")).strip()
            data_chave = data_banco or data
            descricao = str(mov.get("descricao", "")).strip()
            origem = "IMPORTACAO_EXTRATO"

            if deve_ignorar_por_descricao(descricao):
                saldos_ignorados += 1
                itens_saldos.append(resumir_movimentacao_importacao(mov, status="IGNORADO POR SALDO"))
                continue

            if valor_abs <= 0:
                saldos_ignorados += 1
                itens_saldos.append(resumir_movimentacao_importacao(mov, status="VALOR ZERADO"))
                continue

            chave_nova = montar_chave_lancamento(
                data=data_chave,
                descricao=descricao,
                valor=valor_abs,
            )

            if chave_nova in chaves_existentes:
                duplicados_ignorados += 1
                itens_duplicados.append(resumir_movimentacao_importacao(mov, status="JÁ EXISTE NA BASE"))
                continue

            chave_classificacao = montar_chave_classificacao(
                descricao=descricao,
                valor=valor_abs,
            )
            classificacao_reaproveitada = classificacoes_por_descricao_valor.get(chave_classificacao)

            if classificacao_reaproveitada:
                if not categoria_form:
                    categoria_form = str(classificacao_reaproveitada.get("categoria", "")).strip()
                if not subcategoria_form:
                    subcategoria_form = str(classificacao_reaproveitada.get("subcategoria", "")).strip()
                if not tipo_form:
                    tipo_form = str(classificacao_reaproveitada.get("tipo", "")).strip()
                if not situacao:
                    situacao = str(classificacao_reaproveitada.get("situacao", "")).strip()
                if not forma_pagamento:
                    forma_pagamento = str(classificacao_reaproveitada.get("forma_pagamento", "")).strip()
                if not conta:
                    conta = str(classificacao_reaproveitada.get("conta", "")).strip()

                if categoria_form or subcategoria_form:
                    classificacoes_reaproveitadas_importacao += 1

            try:
                tipo, categoria, subcategoria = resolver_categoria_subcategoria_em_memoria(
                    tipo=tipo_form,
                    categoria=categoria_form,
                    subcategoria=subcategoria_form,
                    estrutura=estrutura_categorias_importacao,
                )
            except Exception as erro_validacao:
                return templates.TemplateResponse(
                    request=request,
                    name="extratos.html",
                    context=montar_contexto_extratos(
                        request=request,
                        etapa="previa",
                        erro=(
                            f"Corrija a classificação da movimentação '{descricao}'. "
                            f"Detalhe: {erro_validacao}"
                        ),
                        temp_id=temp_id,
                        resultado=previa,
                    ),
                )

            lancamento = {
                "id": uuid4().hex,
                "data": data,
                "data_banco": data_banco,
                "mes": inferir_mes(data),
                "ano": inferir_ano(data, config.get("ano_base", "")),
                "tipo": tipo,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "descricao": descricao,
                "valor_previsto": "",
                "valor_realizado": f"{valor_abs:.2f}".replace(".", ","),
                "situacao": situacao,
                "forma_pagamento": forma_pagamento,
                "conta": conta,
                "reaproveitar_classificacao": reaproveitar_classificacao,
                "observacao": mov.get("observacao", ""),
                "origem": origem,
            }

            lancamentos.append(lancamento)
            itens_importados.append(
                resumir_movimentacao_importacao(
                    {
                        **mov,
                        "tipo": tipo,
                        "categoria": categoria,
                        "subcategoria": subcategoria,
                        "situacao": situacao,
                        "forma_pagamento": forma_pagamento,
                        "conta": conta,
                    },
                    status="IMPORTADO",
                )
            )
            chaves_existentes.add(chave_nova)

        if not lancamentos and (duplicados_ignorados > 0 or saldos_ignorados > 0):
            mensagem = "Nenhum lançamento novo foi importado."

            if duplicados_ignorados > 0:
                mensagem += f" {duplicados_ignorados} lançamento(s) duplicado(s) foram ignorado(s)."

            if saldos_ignorados > 0:
                mensagem += f" {saldos_ignorados} lançamento(s) de saldo foram ignorado(s)."

            if desmarcados_usuario > 0:
                mensagem += f" {desmarcados_usuario} lançamento(s) desmarcado(s) pelo usuário."

            resultado_importacao = montar_resultado_importacao(
                total_extrato=total_movimentacoes,
                itens_importados=itens_importados,
                itens_duplicados=itens_duplicados,
                itens_saldos=itens_saldos,
                itens_desmarcados=itens_desmarcados,
                classificacoes_reaproveitadas=classificacoes_reaproveitadas_importacao,
            )

            return templates.TemplateResponse(
                request=request,
                name="extratos.html",
                context=montar_contexto_extratos(
                    request=request,
                    etapa="upload",
                    mensagem=mensagem,
                    resultado_importacao=resultado_importacao,
                ),
            )

        if not lancamentos:
            return templates.TemplateResponse(
                request=request,
                name="extratos.html",
                context=montar_contexto_extratos(
                    request=request,
                    etapa="previa",
                    erro="Nenhuma movimentação foi selecionada para importação.",
                    temp_id=temp_id,
                    resultado=previa,
                ),
            )

        url = salvar_lancamentos_em_lote_google(
            link_planilha=link_planilha,
            lancamentos=lancamentos,
        )

        # Cada lançamento recém-importado tenta atualizar automaticamente
        # o pagamento previsto correspondente. A confirmação só ocorre quando
        # há um único candidato com valor, categoria, subcategoria e data
        # compatíveis; os casos ambíguos permanecem para conferência manual.
        resultado_conciliacao_automatica = (
            conciliar_pagamentos_com_lancamentos_importados(
                lancamentos_importados=lancamentos,
            )
        )

        mensagem = (
            f"{len(lancamentos)} lançamento(s) importado(s) com sucesso para a BASE_LANCAMENTOS."
        )

        qtd_pagamentos_auto = int(resultado_conciliacao_automatica.get("atualizados", 0) or 0)
        qtd_pagamentos_ambiguos = int(resultado_conciliacao_automatica.get("ambiguos", 0) or 0)

        if qtd_pagamentos_auto:
            mensagem += (
                f" {qtd_pagamentos_auto} pagamento(s) previsto(s) foram marcado(s) "
                "automaticamente como pago(s)."
            )

        if qtd_pagamentos_ambiguos:
            mensagem += (
                f" {qtd_pagamentos_ambiguos} pagamento(s) ficaram para conferência manual "
                "por haver mais de um candidato compatível."
            )

        if duplicados_ignorados > 0:
            mensagem += f" {duplicados_ignorados} duplicado(s) foram ignorado(s)."

        if saldos_ignorados > 0:
            mensagem += f" {saldos_ignorados} lançamento(s) de saldo foram ignorado(s)."

        if desmarcados_usuario > 0:
            mensagem += f" {desmarcados_usuario} lançamento(s) desmarcado(s) pelo usuário."

        if classificacoes_reaproveitadas_importacao > 0:
            mensagem += f" {classificacoes_reaproveitadas_importacao} classificação(ões) foram reaproveitadas da BASE."

        total_tratado = (
            len(lancamentos)
            + duplicados_ignorados
            + saldos_ignorados
            + desmarcados_usuario
        )

        if total_tratado == total_movimentacoes:
            mensagem += (
                f" Conferência OK: {total_movimentacoes} movimentação(ões) do extrato foram tratadas."
            )
        else:
            mensagem += (
                f" Atenção: o extrato tinha {total_movimentacoes} movimentação(ões), "
                f"mas {total_tratado} foram tratadas entre importadas, duplicadas, saldos e desmarcadas."
            )

        mensagem += f" Planilha: {url}"

        resultado_importacao = montar_resultado_importacao(
            total_extrato=total_movimentacoes,
            itens_importados=itens_importados,
            itens_duplicados=itens_duplicados,
            itens_saldos=itens_saldos,
            itens_desmarcados=itens_desmarcados,
            classificacoes_reaproveitadas=classificacoes_reaproveitadas_importacao,
            url_planilha=url,
        )

        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="upload",
                mensagem=mensagem,
                resultado_importacao=resultado_importacao,
            ),
        )

    except Exception as e:
        try:
            previa = carregar_previa_extrato(temp_id) if temp_id else None
        except Exception:
            previa = None

        return templates.TemplateResponse(
            request=request,
            name="extratos.html",
            context=montar_contexto_extratos(
                request=request,
                etapa="previa" if previa else "upload",
                temp_id=temp_id if previa else None,
                resultado=previa,
                erro=f"Erro ao importar extrato: {e}",
            ),
        )


def montar_contexto_extratos(
    request: Request,
    etapa: str,
    mensagem: str | None = None,
    erro: str | None = None,
    temp_id: str | None = None,
    resultado: dict | None = None,
    resultado_importacao: dict | None = None,
):
    try:
        estrutura_categorias = obter_estrutura_categorias()
    except Exception:
        estrutura_categorias = {}

    return {
        "request": request,
        "etapa": etapa,
        "mensagem": mensagem,
        "erro": erro,
        "temp_id": temp_id,
        "resultado": resultado,
        "resultado_importacao": resultado_importacao,
        "meses": MESES,
        "situacoes": SITUACOES,
        "formas_pagamento": FORMAS_PAGAMENTO,
        "contas": CONTAS,
        "tipos_oficiais": TIPOS_OFICIAIS,
        "estrutura_categorias": estrutura_categorias,
    }


def formatar_valor_tela(valor: float) -> str:
    try:
        numero = abs(float(valor or 0))
    except Exception:
        numero = 0.0

    return f"{numero:.2f}".replace(".", ",")


def resumir_movimentacao_importacao(mov: dict, status: str) -> dict:
    valor = float(mov.get("valor", 0) or 0)

    return {
        "status": status,
        "data": str(mov.get("data", "")).strip(),
        "data_banco": str(mov.get("data_banco", "")).strip(),
        "descricao": str(mov.get("descricao", "")).strip(),
        "valor": abs(valor),
        "valor_fmt": formatar_valor_tela(valor),
        "tipo": str(mov.get("tipo", "")).strip(),
        "categoria": str(mov.get("categoria", "")).strip(),
        "subcategoria": str(mov.get("subcategoria", "")).strip(),
        "situacao": str(mov.get("situacao", "")).strip(),
        "forma_pagamento": str(mov.get("forma_pagamento", "")).strip(),
        "conta": str(mov.get("conta", "")).strip(),
    }


def montar_resultado_importacao(
    total_extrato: int,
    itens_importados: list[dict],
    itens_duplicados: list[dict],
    itens_saldos: list[dict],
    itens_desmarcados: list[dict],
    classificacoes_reaproveitadas: int = 0,
    url_planilha: str = "",
) -> dict:
    qtd_importados = len(itens_importados)
    qtd_duplicados = len(itens_duplicados)
    qtd_saldos = len(itens_saldos)
    qtd_desmarcados = len(itens_desmarcados)

    total_tratado = qtd_importados + qtd_duplicados + qtd_saldos + qtd_desmarcados
    conferencia_ok = total_tratado == int(total_extrato or 0)

    return {
        "total_extrato": int(total_extrato or 0),
        "qtd_importados": qtd_importados,
        "qtd_duplicados": qtd_duplicados,
        "qtd_saldos": qtd_saldos,
        "qtd_desmarcados": qtd_desmarcados,
        "qtd_classificacoes_reaproveitadas": int(classificacoes_reaproveitadas or 0),
        "total_tratado": total_tratado,
        "conferencia_ok": conferencia_ok,
        "url_planilha": url_planilha,
        "itens_importados": itens_importados,
        "itens_duplicados": itens_duplicados,
        "itens_saldos": itens_saldos,
        "itens_desmarcados": itens_desmarcados,
    }


def resolver_categoria_subcategoria_em_memoria(
    tipo: str,
    categoria: str,
    subcategoria: str,
    estrutura: dict,
) -> tuple[str, str, str]:
    """
    Valida TIPO/CATEGORIA/SUBCATEGORIA usando a estrutura já carregada da aba
    CATEGORIAS. Não faz chamadas ao Google Sheets.
    """

    tipo_informado = normalizar_tipo_categoria(tipo)
    categoria_informada = str(categoria or "").strip()
    subcategoria_informada = str(subcategoria or "").strip()

    if tipo_informado not in estrutura:
        raise ValueError(f"Tipo não cadastrado na aba CATEGORIAS: {tipo}")

    categorias_do_tipo = estrutura.get(tipo_informado, {})
    categoria_oficial = resolver_nome_oficial(
        categoria_informada,
        categorias_do_tipo.keys(),
    )

    if not categoria_oficial:
        raise ValueError(
            f"Categoria não cadastrada para {tipo_informado}: {categoria}"
        )

    subcategorias = categorias_do_tipo.get(categoria_oficial, [])

    if not subcategorias:
        return tipo_informado, categoria_oficial, ""

    subcategoria_oficial = resolver_nome_oficial(
        subcategoria_informada,
        subcategorias,
    )

    if not subcategoria_oficial:
        raise ValueError(
            f"Subcategoria não cadastrada para "
            f"{tipo_informado}/{categoria_oficial}: {subcategoria}"
        )

    return tipo_informado, categoria_oficial, subcategoria_oficial


def preparar_resultado_para_categorias_oficiais(resultado: dict) -> dict:
    """
    Mantém as classificações sugeridas por regras quando forem compatíveis
    com a aba CATEGORIAS. Quando não forem, deixa categoria/subcategoria vazias
    para o usuário escolher uma opção oficial na prévia.
    """

    estrutura = obter_estrutura_categorias()
    movimentacoes = resultado.get("movimentacoes", []) or []

    for mov in movimentacoes:
        valor = float(mov.get("valor", 0) or 0)
        tipo_atual = normalizar_tipo_categoria(mov.get("tipo"))

        if tipo_atual not in estrutura:
            tipo_atual = "DESPESA" if valor < 0 else "RECEITA"

        categoria_atual = str(mov.get("categoria", "") or "").strip().upper()
        subcategoria_atual = str(mov.get("subcategoria", "") or "").strip().upper()

        categorias_tipo = estrutura.get(tipo_atual, {})
        categoria_oficial = resolver_nome_oficial(categoria_atual, categorias_tipo.keys())

        if not categoria_oficial:
            mov["tipo"] = tipo_atual
            mov["categoria"] = ""
            mov["subcategoria"] = ""
            continue

        subcategorias = categorias_tipo.get(categoria_oficial, [])
        subcategoria_oficial = resolver_nome_oficial(subcategoria_atual, subcategorias)

        mov["tipo"] = tipo_atual
        mov["categoria"] = categoria_oficial
        mov["subcategoria"] = subcategoria_oficial or ""

    return resultado


def resolver_nome_oficial(valor: str, opcoes) -> str:
    alvo = normalizar_para_chave(valor)

    if not alvo:
        return ""

    for opcao in opcoes:
        if normalizar_para_chave(str(opcao)) == alvo:
            return str(opcao)

    return ""



def atualizar_resumo_conferencia_resultado(resultado: dict) -> dict:
    movimentacoes = resultado.get("movimentacoes", []) or []

    total_extrato = len(movimentacoes)
    ja_existentes = sum(1 for mov in movimentacoes if mov.get("ja_existe_base"))
    reaproveitadas = sum(1 for mov in movimentacoes if mov.get("classificacao_reaproveitada"))
    novos_estimados = max(total_extrato - ja_existentes, 0)

    resultado["resumo_base"] = {
        **(resultado.get("resumo_base", {}) or {}),
        "total_extrato": total_extrato,
        "ja_existentes_base": ja_existentes,
        "classificacoes_reaproveitadas": reaproveitadas,
        "novos_estimados": novos_estimados,
    }

    return resultado


def aplicar_memoria_base_no_resultado(resultado: dict) -> dict:
    """
    Usa a BASE_LANCAMENTOS como memória simples de importação.

    Regras desta primeira versão:
    - se DATA_BANCO/DATA + DESCRIÇÃO normalizada + VALOR já existe na Base,
      marca o movimento como já existente;
    - se DESCRIÇÃO normalizada + VALOR já existe na Base com categoria e
      subcategoria, reaproveita a classificação na prévia;
    - não grava nada na Base nesta etapa.
    """

    contexto_base = obter_contexto_base_lancamentos()
    chaves_existentes = contexto_base.get("chaves", set()) or set()
    classificacoes = contexto_base.get("classificacoes", {}) or {}

    movimentacoes = resultado.get("movimentacoes", []) or []

    for mov in movimentacoes:
        valor_abs = abs(float(mov.get("valor", 0) or 0))
        descricao = str(mov.get("descricao", "")).strip()
        data = str(mov.get("data", "")).strip()
        data_banco = str(mov.get("data_banco", "")).strip()
        data_chave = data_banco or data

        chave_lancamento = montar_chave_lancamento(
            data=data_chave,
            descricao=descricao,
            valor=valor_abs,
        )

        if chave_lancamento in chaves_existentes:
            mov["ja_existe_base"] = True
            mov["status_importacao"] = "JÁ EXISTE NA BASE"
        else:
            mov["ja_existe_base"] = False
            mov["status_importacao"] = "NOVO"

        chave_classificacao = montar_chave_classificacao(
            descricao=descricao,
            valor=valor_abs,
        )
        classificacao = classificacoes.get(chave_classificacao)

        if not classificacao:
            continue

        categoria_atual = str(mov.get("categoria", "") or "").strip()
        subcategoria_atual = str(mov.get("subcategoria", "") or "").strip()

        if not categoria_atual:
            mov["categoria"] = classificacao.get("categoria", "")
        if not subcategoria_atual:
            mov["subcategoria"] = classificacao.get("subcategoria", "")
        if not str(mov.get("tipo", "") or "").strip():
            mov["tipo"] = classificacao.get("tipo", "")
        if not str(mov.get("situacao", "") or "").strip():
            mov["situacao"] = classificacao.get("situacao", "")
        if not str(mov.get("forma_pagamento", "") or "").strip():
            mov["forma_pagamento"] = classificacao.get("forma_pagamento", "")
        if not str(mov.get("conta", "") or "").strip():
            mov["conta"] = classificacao.get("conta", "")

        if mov.get("categoria") or mov.get("subcategoria"):
            mov["classificacao_reaproveitada"] = True
            if not mov.get("ja_existe_base"):
                mov["status_importacao"] = "CLASSIFICAÇÃO REAPROVEITADA"

    return atualizar_resumo_conferencia_resultado(resultado)


def obter_contexto_base_lancamentos() -> dict:
    """
    Monta índices da BASE_LANCAMENTOS para evitar duplicidade e reaproveitar
    classificações já feitas pelo usuário.
    """

    chaves = set()
    classificacoes = {}

    try:
        registros = ler_base_lancamentos()
    except Exception:
        return {"chaves": chaves, "classificacoes": classificacoes}

    for item in registros:
        descricao = str(item.get("DESCRICAO", "")).strip()

        valor_realizado = abs(para_float(item.get("VALOR_REALIZADO")))
        valor_previsto = abs(para_float(item.get("VALOR_PREVISTO")))
        valor = valor_realizado if valor_realizado > 0 else valor_previsto

        if not descricao or valor <= 0:
            continue

        if deve_ignorar_por_descricao(descricao):
            continue

        datas_para_chave = []

        data_banco = str(item.get("DATA_BANCO", "")).strip()
        data = str(item.get("DATA", "")).strip()

        if data_banco:
            datas_para_chave.append(data_banco)
        if data and data not in datas_para_chave:
            datas_para_chave.append(data)

        for data_item in datas_para_chave:
            chaves.add(
                montar_chave_lancamento(
                    data=data_item,
                    descricao=descricao,
                    valor=valor,
                )
            )

        categoria = str(item.get("CATEGORIA", "")).strip()
        subcategoria = str(item.get("SUBCATEGORIA", "")).strip()

        if categoria and subcategoria:
            chave_classificacao = montar_chave_classificacao(
                descricao=descricao,
                valor=valor,
            )

            # Mantém a primeira classificação encontrada para não ficar oscilando
            # se a Base tiver histórico antigo divergente.
            classificacoes.setdefault(
                chave_classificacao,
                {
                    "tipo": str(item.get("TIPO", "")).strip(),
                    "categoria": categoria,
                    "subcategoria": subcategoria,
                    "situacao": str(item.get("SITUACAO", "")).strip(),
                    "forma_pagamento": str(item.get("FORMA_PAGAMENTO", "")).strip(),
                    "conta": str(item.get("CONTA", "")).strip(),
                },
            )

    return {"chaves": chaves, "classificacoes": classificacoes}


def montar_chave_classificacao(
    descricao: str,
    valor: float,
) -> str:
    descricao_norm = normalizar_para_chave(descricao)
    valor_centavos = int(round(abs(float(valor or 0)) * 100))

    return f"{descricao_norm}|{valor_centavos}"


def obter_chaves_lancamentos_existentes() -> set[str]:
    # Mantida para compatibilidade com outras partes do sistema.
    return set(obter_contexto_base_lancamentos().get("chaves", set()))


def montar_chave_lancamento(
    data: str,
    descricao: str,
    valor: float,
) -> str:
    data_norm = normalizar_data_para_chave(data)
    descricao_norm = normalizar_para_chave(descricao)

    valor_centavos = int(round(abs(float(valor or 0)) * 100))

    return f"{data_norm}|{descricao_norm}|{valor_centavos}"


def normalizar_data_para_chave(data: str) -> str:
    texto = str(data or "").strip()

    match_br = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", texto)
    if match_br:
        dia = match_br.group(1).zfill(2)
        mes = match_br.group(2).zfill(2)
        ano = match_br.group(3)

        if len(ano) == 2:
            ano = "20" + ano

        return f"{ano}-{mes}-{dia}"

    match_iso = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})", texto)
    if match_iso:
        ano = match_iso.group(1)
        mes = match_iso.group(2).zfill(2)
        dia = match_iso.group(3).zfill(2)

        return f"{ano}-{mes}-{dia}"

    return normalizar_para_chave(texto)


def normalizar_para_chave(valor: str) -> str:
    texto = str(valor or "").strip().upper()

    substituicoes = {
        "Á": "A",
        "À": "A",
        "Â": "A",
        "Ã": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for origem, destino in substituicoes.items():
        texto = texto.replace(origem, destino)

    texto = re.sub(r"\s+", " ", texto)
    texto = texto.strip()

    return texto


def deve_ignorar_por_descricao(descricao: str) -> bool:
    texto = normalizar_para_chave(descricao)
    texto_sem_espacos = re.sub(r"\s+", "", texto)

    termos = [
        "SALDO",
        "SALDOANTERIOR",
        "SALDOATUAL",
        "SALDODODIA",
        "SALDODISPONIVEL",
        "SALDOBLOQUEADO",
        "SALDOFINAL",
        "SALDOINICIAL",
    ]

    return any(termo in texto_sem_espacos for termo in termos)


def inferir_mes(data_texto: str) -> str:
    texto = str(data_texto or "").strip()

    mapa = {
        "01": "JAN",
        "02": "FEV",
        "03": "MAR",
        "04": "ABR",
        "05": "MAI",
        "06": "JUN",
        "07": "JUL",
        "08": "AGO",
        "09": "SET",
        "10": "OUT",
        "11": "NOV",
        "12": "DEZ",
    }

    match_br = re.match(r"^\d{1,2}[/-](\d{1,2})[/-]\d{2,4}", texto)
    if match_br:
        mes = match_br.group(1).zfill(2)
        return mapa.get(mes, "")

    match_iso = re.match(r"^\d{4}[/-](\d{1,2})[/-]\d{1,2}", texto)
    if match_iso:
        mes = match_iso.group(1).zfill(2)
        return mapa.get(mes, "")

    return ""


def inferir_ano(data_texto: str, ano_padrao: str | int) -> str:
    texto = str(data_texto or "").strip()

    match_br = re.match(r"^\d{1,2}[/-]\d{1,2}[/-](\d{2,4})", texto)
    if match_br:
        ano = match_br.group(1)
        if len(ano) == 2:
            return "20" + ano
        return ano

    match_iso = re.match(r"^(\d{4})[/-]\d{1,2}[/-]\d{1,2}", texto)
    if match_iso:
        return match_iso.group(1)

    return str(ano_padrao or "")
