from typing import Optional

from pydantic import BaseModel


class MetaPrincipalMobile(BaseModel):
    nome: str
    valor_atual: float
    valor_alvo: float
    percentual: float


class CardDashboardMobile(BaseModel):
    titulo: str
    valor: float
    tipo: str
    icone: str
    quantidade: Optional[int] = None
    valor_alvo: Optional[float] = None
    percentual: Optional[float] = None


class AcaoRapidaMobile(BaseModel):
    titulo: str
    tipo: str
    rota: str


class DashboardMobile(BaseModel):
    mes: str
    saldo_mes: float
    receitas: float
    despesas: float
    contas_pendentes: int
    total_pendente: float
    patrimonio_total: float
    meta_principal: Optional[MetaPrincipalMobile] = None
    cards: list[CardDashboardMobile]
    acoes_rapidas: list[AcaoRapidaMobile]