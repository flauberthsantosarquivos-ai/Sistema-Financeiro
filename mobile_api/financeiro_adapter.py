from datetime import date
from typing import Any


def normalizar_valor(valor: Any) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )

    try:
        return float(texto)
    except ValueError:
        return 0.0


def obter_periodo_padrao(
    ano: int | None = None,
    mes: int | None = None,
) -> tuple[int, int]:
    hoje = date.today()
    return ano or hoje.year, mes or hoje.month


def montar_referencia(ano: int, mes: int) -> str:
    return f"{ano}-{mes:02d}"