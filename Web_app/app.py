from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.financeiro.configuracao_sistema import configuracao_runtime_existe
from Web_app.routes_base_lancamentos import router as router_base_lancamentos
from Web_app.routes_configuracoes import router as router_configuracoes
from Web_app.routes_extratos import router as router_extratos
from Web_app.routes_financeiro import router as router_financeiro
from Web_app.routes_lancamentos import router as router_lancamentos
from Web_app.routes_planejamento import router as router_planejamento

app = FastAPI(
    title="Sistema Financeiro",
    description="Sistema Financeiro com dashboard, planejamento mensal, lançamentos e importação de extratos",
    version="1.0.0",
)

templates = Jinja2Templates(directory="Web_app/templates")

app.include_router(router_financeiro)
app.include_router(router_lancamentos)
app.include_router(router_planejamento)
app.include_router(router_configuracoes)
app.include_router(router_extratos)
app.include_router(router_base_lancamentos)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not configuracao_runtime_existe():
        return RedirectResponse(url="/financeiro/configuracoes", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "titulo": "Sistema Financeiro",
        },
    )