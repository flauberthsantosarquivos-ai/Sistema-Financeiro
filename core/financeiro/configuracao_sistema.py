from __future__ import annotations

import json
from pathlib import Path

from config_financeiro import (
    ANO_BASE_PADRAO,
    CONTA_ALIMENTACAO_PADRAO,
    CONTA_PRINCIPAL_PADRAO,
    META_RESERVA_PERCENTUAL,
    NOME_CLIENTE_PADRAO,
    PLANILHA_GOOGLE_PADRAO,
    RECEITA_PADRAO,
)


ARQUIVO_CONFIG_RUNTIME = Path("config_runtime_financeiro.json")


def configuracao_runtime_existe() -> bool:
    return ARQUIVO_CONFIG_RUNTIME.exists()


def obter_configuracao_sistema() -> dict:
    config = {
        "nome_cliente": NOME_CLIENTE_PADRAO,
        "ano_base": ANO_BASE_PADRAO,
        "receita_padrao": RECEITA_PADRAO,
        "conta_principal": CONTA_PRINCIPAL_PADRAO,
        "conta_alimentacao": CONTA_ALIMENTACAO_PADRAO,
        "meta_reserva": META_RESERVA_PERCENTUAL,
        "planilha_google": PLANILHA_GOOGLE_PADRAO,
    }

    if ARQUIVO_CONFIG_RUNTIME.exists():
        try:
            dados = json.loads(ARQUIVO_CONFIG_RUNTIME.read_text(encoding="utf-8"))
            config.update(dados)
        except Exception:
            pass

    return config


def salvar_planilha_vinculada(
    nome_cliente: str,
    ano_base: int,
    receita_padrao: str,
    conta_principal: str,
    conta_alimentacao: str,
    meta_reserva: str,
    planilha_google: str,
) -> None:
    dados = {
        "nome_cliente": nome_cliente,
        "ano_base": ano_base,
        "receita_padrao": receita_padrao,
        "conta_principal": conta_principal,
        "conta_alimentacao": conta_alimentacao,
        "meta_reserva": meta_reserva,
        "planilha_google": planilha_google,
    }

    ARQUIVO_CONFIG_RUNTIME.write_text(
        json.dumps(dados, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )