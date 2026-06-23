from __future__ import annotations

from importlib import import_module
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from mobile_api.routes import router as mobile_router


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


app = FastAPI(
    title="Sistema Financeiro",
    description="Sistema de gestão financeira com extratos, lançamentos, orçamento, configurações e análise.",
    version="1.0.0",
)

# Liberação temporária para desenvolvimento local com Flutter Web/Chrome.
# Depois, quando o app estiver mais avançado, podemos restringir as origens.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mobile_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


ROTAS_DO_SISTEMA = [
    "Web_app.routes_financeiro",
    "Web_app.routes_configuracoes",
    "Web_app.routes_extratos",
    "Web_app.routes_base_lancamentos",
    "Web_app.routes_lancamentos",
    "Web_app.routes_orcamento",
    "Web_app.routes_pagamentos",
    "Web_app.routes_patrimonio",
    "Web_app.routes_investimentos",
    "Web_app.routes_metas",
    "Web_app.routes_alimentacao",
]


for modulo_nome in ROTAS_DO_SISTEMA:
    try:
        modulo = import_module(modulo_nome)
        router = getattr(modulo, "router", None)

        if router is not None:
            app.include_router(router)
            print(f"Rota carregada: {modulo_nome}")

    except ModuleNotFoundError as e:
        print(f"Rota não encontrada, ignorando: {modulo_nome}")
        print(f"Detalhe do erro: {e}")

    except Exception as e:
        print(f"Erro ao carregar rota {modulo_nome}: {e}")


@app.get("/")
async def index():
    return RedirectResponse(url="/financeiro", status_code=303)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "sistema": "Sistema Financeiro",
    }