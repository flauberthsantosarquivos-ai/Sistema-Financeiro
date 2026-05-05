from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from openpyxl import load_workbook


PASTA_EXTRATOS = Path("uploads/extratos")
PASTA_EXTRATOS.mkdir(parents=True, exist_ok=True)


COLUNAS_DATA = {
    "data",
    "dt",
    "data lancamento",
    "data lançamento",
    "lancamento",
    "lançamento",
    "date",
}

COLUNAS_DESCRICAO = {
    "descricao",
    "descrição",
    "historico",
    "histórico",
    "documento",
    "detalhe",
    "detalhes",
    "memo",
    "lançamento",
    "lancamento",
    "nome",
}

COLUNAS_VALOR = {
    "valor",
    "vlr",
    "amount",
    "movimentacao",
    "movimentação",
    "debito",
    "débito",
    "credito",
    "crédito",
    "entrada",
    "saida",
    "saída",
}


REGRAS_CLASSIFICACAO = [
    {
        "termos": ["SUPERMERCADO", "MERCADO", "ASSAI", "ASSAÍ", "MATEUS", "ATACADAO", "ATACADÃO", "CARREFOUR"],
        "tipo": "DESPESA",
        "categoria": "ALIMENTAÇÃO",
        "subcategoria": "SUPERMERCADO",
    },
    {
        "termos": ["RESTAURANTE", "LANCHONETE", "IFOOD", "DELIVERY", "PIZZARIA", "BURGER", "HAMBURGUER"],
        "tipo": "DESPESA",
        "categoria": "ALIMENTAÇÃO",
        "subcategoria": "RESTAURANTE",
    },
    {
        "termos": ["POSTO", "COMBUSTIVEL", "COMBUSTÍVEL", "GASOLINA", "ETANOL", "SHELL", "IPIRANGA", "PETROBRAS"],
        "tipo": "DESPESA",
        "categoria": "TRANSPORTE",
        "subcategoria": "COMBUSTÍVEL",
    },
    {
        "termos": ["ENERGIA", "EQUATORIAL", "ENEL", "LUZ"],
        "tipo": "DESPESA",
        "categoria": "CASA",
        "subcategoria": "ENERGIA ELÉTRICA",
    },
    {
        "termos": ["AGUA", "ÁGUA", "CAEMA", "SANEAMENTO"],
        "tipo": "DESPESA",
        "categoria": "CASA",
        "subcategoria": "ÁGUA",
    },
    {
        "termos": ["INTERNET", "CLARO", "VIVO", "TIM", "OI", "NET", "FIBRA"],
        "tipo": "DESPESA",
        "categoria": "COMUNICAÇÃO",
        "subcategoria": "INTERNET",
    },
    {
        "termos": ["ESCOLA", "COLÉGIO", "COLEGIO", "MENSALIDADE", "EDUCAÇÃO", "EDUCACAO"],
        "tipo": "DESPESA",
        "categoria": "EDUCAÇÃO",
        "subcategoria": "ESCOLA",
    },
    {
        "termos": ["FARMACIA", "FARMÁCIA", "DROGARIA", "RAIA", "PAGUE MENOS", "ULTRAFARMA"],
        "tipo": "DESPESA",
        "categoria": "SAÚDE",
        "subcategoria": "FARMÁCIA",
    },
    {
        "termos": ["PLANO DE SAUDE", "PLANO DE SAÚDE", "UNIMED", "HAPVIDA", "AMIL"],
        "tipo": "DESPESA",
        "categoria": "SAÚDE",
        "subcategoria": "PLANO DE SAÚDE",
    },
    {
        "termos": ["SALARIO", "SALÁRIO", "REMUNERACAO", "REMUNERAÇÃO", "TRE"],
        "tipo": "RECEITA",
        "categoria": "SALÁRIO",
        "subcategoria": "TRE",
    },
    {
        "termos": ["PIX RECEBIDO", "TED RECEBIDA", "TRANSFERENCIA RECEBIDA", "TRANSFERÊNCIA RECEBIDA"],
        "tipo": "RECEITA",
        "categoria": "OUTRAS RECEITAS",
        "subcategoria": "DIVERSOS",
    },
]


def normalizar_texto(texto: Any) -> str:
    if texto is None:
        return ""

    texto = str(texto).strip().lower()
    texto = texto.replace("ç", "c")
    texto = texto.replace("ã", "a")
    texto = texto.replace("á", "a")
    texto = texto.replace("à", "a")
    texto = texto.replace("â", "a")
    texto = texto.replace("é", "e")
    texto = texto.replace("ê", "e")
    texto = texto.replace("í", "i")
    texto = texto.replace("ó", "o")
    texto = texto.replace("ô", "o")
    texto = texto.replace("õ", "o")
    texto = texto.replace("ú", "u")
    texto = re.sub(r"\s+", " ", texto)

    return texto


def normalizar_cabecalho(valor: Any) -> str:
    texto = normalizar_texto(valor)
    texto = texto.replace("_", " ")
    texto = texto.replace("-", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def converter_valor(valor: Any) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    if not texto:
        return 0.0

    negativo_por_parenteses = texto.startswith("(") and texto.endswith(")")

    texto = texto.replace("R$", "")
    texto = texto.replace(" ", "")
    texto = texto.replace("(", "")
    texto = texto.replace(")", "")

    # Remove símbolos comuns de extrato
    texto = texto.replace("+", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    texto = re.sub(r"[^0-9\.-]", "", texto)

    if texto in {"", "-", ".", "-."}:
        return 0.0

    try:
        numero = float(texto)
    except ValueError:
        return 0.0

    if negativo_por_parenteses:
        numero = -abs(numero)

    return numero


def valor_para_texto_brasil(valor: float) -> str:
    return f"{abs(valor):.2f}".replace(".", ",")


def detectar_delimitador(caminho: Path) -> str:
    amostra = caminho.read_text(encoding="utf-8", errors="ignore")[:4096]

    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=";,|\t,")
        return dialect.delimiter
    except Exception:
        if ";" in amostra:
            return ";"
        return ","


def ler_csv(caminho: Path) -> list[dict[str, Any]]:
    delimitador = detectar_delimitador(caminho)

    for encoding in ["utf-8-sig", "latin-1", "cp1252"]:
        try:
            with caminho.open("r", encoding=encoding, newline="") as arquivo:
                leitor = csv.DictReader(arquivo, delimiter=delimitador)
                return [dict(linha) for linha in leitor]
        except UnicodeDecodeError:
            continue

    with caminho.open("r", encoding="utf-8", errors="ignore", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=delimitador)
        return [dict(linha) for linha in leitor]


def ler_excel(caminho: Path) -> list[dict[str, Any]]:
    wb = load_workbook(caminho, data_only=True)
    ws = wb[wb.sheetnames[0]]

    linhas = list(ws.iter_rows(values_only=True))

    if not linhas:
        return []

    cabecalhos = [str(c or "").strip() for c in linhas[0]]
    registros = []

    for linha in linhas[1:]:
        if not any(celula is not None and str(celula).strip() for celula in linha):
            continue

        registro = {}

        for indice, cabecalho in enumerate(cabecalhos):
            if not cabecalho:
                continue

            registro[cabecalho] = linha[indice] if indice < len(linha) else ""

        registros.append(registro)

    return registros


def encontrar_coluna(cabecalhos: list[str], candidatos: set[str]) -> str | None:
    for cabecalho in cabecalhos:
        normalizado = normalizar_cabecalho(cabecalho)

        if normalizado in candidatos:
            return cabecalho

    for cabecalho in cabecalhos:
        normalizado = normalizar_cabecalho(cabecalho)

        for candidato in candidatos:
            if candidato in normalizado or normalizado in candidato:
                return cabecalho

    return None


def detectar_colunas(registros: list[dict[str, Any]]) -> tuple[str | None, str | None, str | None]:
    if not registros:
        return None, None, None

    cabecalhos = list(registros[0].keys())

    coluna_data = encontrar_coluna(cabecalhos, COLUNAS_DATA)
    coluna_descricao = encontrar_coluna(cabecalhos, COLUNAS_DESCRICAO)
    coluna_valor = encontrar_coluna(cabecalhos, COLUNAS_VALOR)

    # Caso comum: extrato com colunas separadas débito/crédito
    if not coluna_valor:
        debito = encontrar_coluna(cabecalhos, {"debito", "débito", "saida", "saída"})
        credito = encontrar_coluna(cabecalhos, {"credito", "crédito", "entrada"})

        if debito or credito:
            coluna_valor = "__DEBITO_CREDITO__"

    return coluna_data, coluna_descricao, coluna_valor


def obter_valor_registro(registro: dict[str, Any], coluna_valor: str | None) -> float:
    if not coluna_valor:
        return 0.0

    if coluna_valor == "__DEBITO_CREDITO__":
        debito = None
        credito = None

        for chave in registro.keys():
            chave_normalizada = normalizar_cabecalho(chave)

            if chave_normalizada in {"debito", "saida"}:
                debito = registro.get(chave)

            if chave_normalizada in {"credito", "entrada"}:
                credito = registro.get(chave)

        valor_debito = converter_valor(debito)
        valor_credito = converter_valor(credito)

        if valor_debito:
            return -abs(valor_debito)

        if valor_credito:
            return abs(valor_credito)

        return 0.0

    return converter_valor(registro.get(coluna_valor))


def classificar_movimentacao(descricao: str, valor: float) -> dict[str, str]:
    descricao_upper = descricao.upper()

    for regra in REGRAS_CLASSIFICACAO:
        for termo in regra["termos"]:
            if termo.upper() in descricao_upper:
                return {
                    "tipo": regra["tipo"],
                    "categoria": regra["categoria"],
                    "subcategoria": regra["subcategoria"],
                }

    if valor > 0:
        return {
            "tipo": "RECEITA",
            "categoria": "OUTRAS RECEITAS",
            "subcategoria": "DIVERSOS",
        }

    return {
        "tipo": "DESPESA",
        "categoria": "OUTROS",
        "subcategoria": "DIVERSOS",
    }


def processar_extrato(caminho: str | Path) -> dict[str, Any]:
    caminho = Path(caminho)

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    extensao = caminho.suffix.lower()

    if extensao == ".csv":
        registros = ler_csv(caminho)
    elif extensao in {".xlsx", ".xls"}:
        registros = ler_excel(caminho)
    else:
        raise ValueError("Formato ainda não suportado para leitura automática. Use CSV, XLS ou XLSX.")

    if not registros:
        return {
            "movimentacoes": [],
            "colunas_detectadas": {},
            "total_linhas": 0,
        }

    coluna_data, coluna_descricao, coluna_valor = detectar_colunas(registros)

    movimentacoes = []

    for indice, registro in enumerate(registros, start=1):
        data = str(registro.get(coluna_data, "")).strip() if coluna_data else ""
        descricao = str(registro.get(coluna_descricao, "")).strip() if coluna_descricao else ""
        valor = obter_valor_registro(registro, coluna_valor)

        if not descricao and valor == 0:
            continue

        classificacao = classificar_movimentacao(descricao, valor)

        movimentacoes.append(
            {
                "indice": len(movimentacoes),
                "linha_original": indice,
                "data": data,
                "descricao": descricao or "Movimentação sem descrição",
                "valor": valor,
                "valor_fmt": valor_para_texto_brasil(valor),
                "tipo": classificacao["tipo"],
                "categoria": classificacao["categoria"],
                "subcategoria": classificacao["subcategoria"],
                "situacao": "PAGO" if valor < 0 else "RECEBIDO",
                "forma_pagamento": "CONTA",
                "conta": "BANCO PRINCIPAL",
                "observacao": f"Importado do extrato: {caminho.name}",
            }
        )

    return {
        "movimentacoes": movimentacoes,
        "colunas_detectadas": {
            "data": coluna_data,
            "descricao": coluna_descricao,
            "valor": coluna_valor,
        },
        "total_linhas": len(registros),
    }


def salvar_previa_extrato(dados: dict[str, Any]) -> str:
    temp_id = uuid4().hex
    caminho = PASTA_EXTRATOS / f"{temp_id}.json"

    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return temp_id


def carregar_previa_extrato(temp_id: str) -> dict[str, Any]:
    caminho = PASTA_EXTRATOS / f"{temp_id}.json"

    if not caminho.exists():
        raise FileNotFoundError("Prévia do extrato não encontrada. Importe o arquivo novamente.")

    return json.loads(caminho.read_text(encoding="utf-8"))