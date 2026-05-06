from __future__ import annotations

from importlib import import_module
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


app = FastAPI(
    title="Sistema Financeiro",
    description="Sistema de gestão financeira com extratos, lançamentos, orçamento e análise.",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


ROTAS_DO_SISTEMA = [
    "Web_app.routes_financeiro",
    "Web_app.routes_extratos",
    "Web_app.routes_base_lancamentos",
    "Web_app.routes_orcamento",
]


for modulo_nome in ROTAS_DO_SISTEMA:
    try:
        modulo = import_module(modulo_nome)
        router = getattr(modulo, "router", None)

        if router is not None:
            app.include_router(router)

    except ModuleNotFoundError:
        print(f"Rota não encontrada, ignorando: {modulo_nome}")

    except Exception as e:
        print(f"Erro ao carregar rota {modulo_nome}: {e}")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/financeiro", status_code=303)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "sistema": "Sistema Financeiro",
    }