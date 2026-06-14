from fastapi import APIRouter

router = APIRouter(
    prefix="/api/mobile",
    tags=["Mobile"],
)


@router.get("/status")
def status_mobile():
    return {
        "status": "online",
        "modulo": "mobile",
        "mensagem": "API mobile do Sistema Financeiro funcionando",
    }


@router.get("/dashboard")
def dashboard_mobile():
    return {
        "mes": "2026-06",
        "saldo_mes": 1250.75,
        "receitas": 6200.00,
        "despesas": 4949.25,
        "contas_pendentes": 8,
        "total_pendente": 1370.00,
        "patrimonio_total": 38500.00,
        "meta_principal": {
            "nome": "Reserva de emergência",
            "valor_atual": 7200.00,
            "valor_alvo": 10000.00,
            "percentual": 72,
        },
    }