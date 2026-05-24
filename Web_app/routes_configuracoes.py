from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import (
    configuracao_runtime_existe,
    obter_configuracao_sistema,
    salvar_planilha_vinculada,
)
from core.financeiro.planilha_padrao import criar_planilha_padrao_financeira
from core.financeiro.categorias_google import (
    alterar_status_categoria,
    listar_categorias,
    obter_estrutura_categorias,
    salvar_categoria,
)


router = APIRouter()

templates = Jinja2Templates(directory="Web_app/templates")


def montar_contexto_configuracoes(
    mensagem: str | None = None,
    erro: str | None = None,
    nova_planilha_url: str | None = None,
    status_google: str = "Configuração local identificada",
):
    config = obter_configuracao_sistema()

    categorias = []
    categorias_estrutura = {}

    try:
        if str(config.get("planilha_google", "") or "").strip():
            categorias = listar_categorias(incluir_inativas=True)
            categorias_estrutura = obter_estrutura_categorias(incluir_inativas=False)

    except Exception as e:
        erro = erro or f"Erro ao carregar categorias: {e}"

    return {
        **config,
        "status_google": status_google,
        "mensagem": mensagem,
        "erro": erro,
        "nova_planilha_url": nova_planilha_url,
        "configuracao_existente": configuracao_runtime_existe(),
        "categorias": categorias,
        "categorias_estrutura": categorias_estrutura,
        "tipos_categoria": [
            "RECEITA",
            "DESPESA",
            "INVESTIMENTO",
            "TRANSFERÊNCIA",
        ],
    }


@router.get("/financeiro/configuracoes", response_class=HTMLResponse)
async def configuracoes_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="configuracoes.html",
        context=montar_contexto_configuracoes(),
    )


@router.post("/financeiro/configuracoes/criar-planilha", response_class=HTMLResponse)
async def criar_planilha_post(
    request: Request,
    nome_cliente: str = Form(...),
    ano_base: int = Form(...),
    receita_padrao: str = Form(...),
    conta_principal: str = Form(...),
    conta_alimentacao: str = Form(...),
    meta_reserva: str = Form(...),
    confirmar_recriacao: str = Form("NAO"),
):
    try:
        if configuracao_runtime_existe() and confirmar_recriacao != "SIM":
            return templates.TemplateResponse(
                request=request,
                name="configuracoes.html",
                context=montar_contexto_configuracoes(
                    erro=(
                        "Já existe uma planilha vinculada ao sistema. "
                        "Criar uma nova planilha altera a estrutura principal usada por Planejamento, "
                        "Novo Lançamento, Importar Extrato e Dashboard. "
                        "Marque a confirmação para criar uma nova planilha mesmo assim."
                    ),
                    status_google="Configuração existente protegida",
                ),
            )

        resultado = criar_planilha_padrao_financeira(
            nome_cliente=nome_cliente,
            ano_base=ano_base,
            receita_padrao=receita_padrao,
            conta_principal=conta_principal,
            conta_alimentacao=conta_alimentacao,
            meta_reserva=meta_reserva,
        )

        salvar_planilha_vinculada(
            nome_cliente=nome_cliente,
            ano_base=ano_base,
            receita_padrao=receita_padrao,
            conta_principal=conta_principal,
            conta_alimentacao=conta_alimentacao,
            meta_reserva=meta_reserva,
            planilha_google=resultado["url"],
        )

        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                mensagem=f"Planilha padrão criada com sucesso: {resultado['nome']}",
                nova_planilha_url=resultado["url"],
                status_google="Nova planilha criada e vinculada",
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                erro=f"Erro ao criar planilha padrão: {e}",
                status_google="Erro ao criar planilha",
            ),
        )


@router.post("/financeiro/configuracoes/categorias/salvar", response_class=HTMLResponse)
async def salvar_categoria_post(
    request: Request,
    tipo: str = Form(...),
    categoria: str = Form(...),
    subcategoria: str = Form(...),
    ativo: str = Form("SIM"),
):
    try:
        item = salvar_categoria(
            tipo=tipo,
            categoria=categoria,
            subcategoria=subcategoria,
            ativo=ativo,
        )

        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                mensagem=(
                    "Categoria salva com sucesso: "
                    f"{item['TIPO']} / {item['CATEGORIA']} / {item['SUBCATEGORIA']}"
                ),
                status_google="Categorias atualizadas",
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                erro=f"Erro ao salvar categoria: {e}",
                status_google="Erro ao salvar categoria",
            ),
        )


@router.post("/financeiro/configuracoes/categorias/{linha}/ativar", response_class=HTMLResponse)
async def ativar_categoria_post(request: Request, linha: int):
    try:
        alterar_status_categoria(linha=linha, ativo="SIM")

        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                mensagem="Categoria ativada com sucesso.",
                status_google="Categorias atualizadas",
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                erro=f"Erro ao ativar categoria: {e}",
                status_google="Erro ao ativar categoria",
            ),
        )


@router.post("/financeiro/configuracoes/categorias/{linha}/desativar", response_class=HTMLResponse)
async def desativar_categoria_post(request: Request, linha: int):
    try:
        alterar_status_categoria(linha=linha, ativo="NÃO")

        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                mensagem="Categoria desativada com sucesso.",
                status_google="Categorias atualizadas",
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="configuracoes.html",
            context=montar_contexto_configuracoes(
                erro=f"Erro ao desativar categoria: {e}",
                status_google="Erro ao desativar categoria",
            ),
        )
