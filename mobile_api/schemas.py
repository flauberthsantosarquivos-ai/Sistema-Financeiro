from typing import Optional

from pydantic import BaseModel


class MetaPrincipalMobile(BaseModel):
    nome: str
    valor_atual: float
    valor_alvo: float
    percentual: float


class DashboardMobile(BaseModel):
    mes: str
    saldo_mes: float
    receitas: float
    despesas: float
    contas_pendentes: int
    total_pendente: float
    patrimonio_total: float
    meta_principal: Optional[MetaPrincipalMobile] = None