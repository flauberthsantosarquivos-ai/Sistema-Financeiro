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

COLUNAS_CATEGORIA_BANCO = {
    "categoria",
    "categoria banco",
    "classificacao",
    "classificação",
    "grupo",
    "tipo despesa",
    "tipo categoria",
}

COLUNAS_TIPO_LANCAMENTO = {
    "tipo lancamento",
    "tipo lançamento",
    "tipo",
    "entrada saida",
    "entrada saída",
}


REGRAS_CLASSIFICACAO = [
    {
        "termos": [
            "SALDO",
            "S A L D O",
            "SALDO ANTERIOR",
            "SALDO ATUAL",
            "SALDO DO DIA",
            "SALDO DISPONIVEL",
            "SALDO DISPONÍVEL",
            "SALDO BLOQUEADO",
            "SALDO FINAL",
            "SALDO INICIAL",
        ],
        "ignorar": True,
    },

    # Regra de segurança do sistema:
    # Pix enviado sem regra específica do cliente não deve cair em transporte.
    # As regras específicas do cliente, na aba REGRAS_CLASSIFICACAO, continuam tendo prioridade final,
    # pois são aplicadas na prévia depois da leitura do extrato.
    {
        "termos": [
            "PIX - ENVIADO",
            "PIX ENVIADO",
            "PIX TRANSF",
            "PIX TRANSFERENCIA",
            "PIX TRANSFERÊNCIA",
            "PIX PARA",
            "PAGAMENTO PIX",
        ],
        "tipo": "TRANSFERÊNCIA",
        "categoria": "TRANSFERÊNCIA VIA PIX",
        "subcategoria": "A CLASSIFICAR",
    },

    {
        "termos": ["ESTACIONAMENTO", "PARKING"],
        "tipo": "DESPESA",
        "categoria": "TRANSPORTE",
        "subcategoria": "ESTACIONAMENTO",
    },
    {
        "termos": [
            "SUPERMERCADO",
            "MERCADO",
            "ASSAI",
            "ASSAÍ",
            "MATEUS",
            "ATACADAO",
            "ATACADÃO",
            "CARREFOUR",
        ],
        "tipo": "DESPESA",
        "categoria": "ALIMENTAÇÃO",
        "subcategoria": "SUPERMERCADO",
    },
    {
        "termos": [
            "RESTAURANTE",
            "LANCHONETE",
            "IFOOD",
            "DELIVERY",
            "PIZZARIA",
            "BURGER",
            "HAMBURGUER",
        ],
        "tipo": "DESPESA",
        "categoria": "ALIMENTAÇÃO",
        "subcategoria": "RESTAURANTE",
    },
    {
        "termos": ["PADARIA", "PANIFICADORA"],
        "tipo": "DESPESA",
        "categoria": "ALIMENTAÇÃO",
        "subcategoria": "PADARIA",
    },
    {
        "termos": ["HORTIFRUTI", "FLV", "FEIRA", "SACOLAO", "SACOLÃO"],
        "tipo": "DESPESA",
        "categoria": "ALIMENTAÇÃO",
        "subcategoria": "FLV",
    },
    {
        "termos": [
            "POSTO",
            "COMBUSTIVEL",
            "COMBUSTÍVEL",
            "GASOLINA",
            "ETANOL",
            "SHELL",
            "IPIRANGA",
            "PETROBRAS",
        ],
        "tipo": "DESPESA",
        "categoria": "TRANSPORTE",
        "subcategoria": "COMBUSTÍVEL",
    },
    {
        "termos": ["UBER", "99APP", "99 APP", "TAXI", "TÁXI"],
        "tipo": "DESPESA",
        "categoria": "TRANSPORTE",
        "subcategoria": "APLICATIVO / TÁXI",
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
        "termos": ["CONDOMINIO", "CONDOMÍNIO", "CONDOM"],
        "tipo": "DESPESA",
        "categoria": "CASA",
        "subcategoria": "CONDOMÍNIO",
    },
    {
        "termos": ["INTERNET", "CLARO", "VIVO", "TIM", "OI", "NET", "FIBRA"],
        "tipo": "DESPESA",
        "categoria": "COMUNICAÇÃO",
        "subcategoria": "INTERNET / TELEFONE",
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
        "termos": [
            "PIX RECEBIDO",
            "TED RECEBIDA",
            "TRANSFERENCIA RECEBIDA",
            "TRANSFERÊNCIA RECEBIDA",
            "CREDITO PIX",
            "CRÉDITO PIX",
        ],
        "tipo": "RECEITA",
        "categoria": "OUTRAS RECEITAS",
        "subcategoria": "DIVERSOS",
    },
    {
        "termos": [
            "TRANSFERENCIA",
            "TRANSFERÊNCIA",
            "TRANSF ENTRE CONTAS",
            "RESGATE",
            "APLICACAO",
            "APLICAÇÃO",
        ],
        "tipo": "TRANSFERÊNCIA",
        "categoria": "TRANSFERÊNCIA ENTRE CONTAS",
        "subcategoria": "MOVIMENTAÇÃO ENTRE CONTAS",
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


def normalizar_para_comparacao(valor: Any) -> str:
    texto = str(valor or "").upper()

    substituicoes = {
        "Á": "A",
        "À": "A",
        "Â": "A",
        "Ã": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for origem, destino in substituicoes.items():
        texto = texto.replace(origem, destino)

    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


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

    indice_cabecalho = detectar_linha_cabecalho(linhas)

    if indice_cabecalho is None:
        indice_cabecalho = 0

    cabecalhos = [str(c or "").strip() for c in linhas[indice_cabecalho]]
    registros = []

    for linha in linhas[indice_cabecalho + 1:]:
        if not any(celula is not None and str(celula).strip() for celula in linha):
            continue

        registro = {}

        for indice, cabecalho in enumerate(cabecalhos):
            if not cabecalho:
                continue

            registro[cabecalho] = linha[indice] if indice < len(linha) else ""

        registros.append(registro)

    return registros


def detectar_linha_cabecalho(linhas: list[tuple[Any, ...]]) -> int | None:
    for indice, linha in enumerate(linhas[:20]):
        normalizados = {normalizar_cabecalho(celula) for celula in linha if celula is not None}

        tem_data = bool(normalizados.intersection(COLUNAS_DATA))
        tem_valor = bool(normalizados.intersection(COLUNAS_VALOR))
        tem_descricao = bool(normalizados.intersection(COLUNAS_DESCRICAO))

        if tem_data and tem_valor and tem_descricao:
            return indice

    return None


def encontrar_coluna(cabecalhos: list[str], candidatos: set[str]) -> str | None:
    for cabecalho in cabecalhos:
        normalizado = normalizar_cabecalho(cabecalho)

        if normalizado in candidatos:
            return cabecalho

    for cabecalho in cabecalhos:
        normalizado = normalizar_cabecalho(cabecalho)

        for candidato in candidatos:
            candidato_normalizado = normalizar_cabecalho(candidato)

            if candidato_normalizado in normalizado or normalizado in candidato_normalizado:
                return cabecalho

    return None


def detectar_colunas(registros: list[dict[str, Any]]) -> dict[str, str | None]:
    if not registros:
        return {
            "data": None,
            "descricao": None,
            "valor": None,
            "categoria_banco": None,
            "tipo_lancamento": None,
            "bb_lancamento": None,
            "bb_detalhes": None,
        }

    cabecalhos = list(registros[0].keys())

    coluna_data = encontrar_coluna(cabecalhos, COLUNAS_DATA)
    coluna_descricao = encontrar_coluna(cabecalhos, COLUNAS_DESCRICAO)
    coluna_valor = encontrar_coluna(cabecalhos, COLUNAS_VALOR)
    coluna_categoria_banco = encontrar_coluna(cabecalhos, COLUNAS_CATEGORIA_BANCO)
    coluna_tipo_lancamento = encontrar_coluna(cabecalhos, COLUNAS_TIPO_LANCAMENTO)

    coluna_bb_lancamento = encontrar_coluna(cabecalhos, {"lancamento", "lançamento"})
    coluna_bb_detalhes = encontrar_coluna(cabecalhos, {"detalhes", "detalhe"})

    if not coluna_valor:
        debito = encontrar_coluna(cabecalhos, {"debito", "débito", "saida", "saída"})
        credito = encontrar_coluna(cabecalhos, {"credito", "crédito", "entrada"})

        if debito or credito:
            coluna_valor = "__DEBITO_CREDITO__"

    return {
        "data": coluna_data,
        "descricao": coluna_descricao,
        "valor": coluna_valor,
        "categoria_banco": coluna_categoria_banco,
        "tipo_lancamento": coluna_tipo_lancamento,
        "bb_lancamento": coluna_bb_lancamento,
        "bb_detalhes": coluna_bb_detalhes,
    }


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


def montar_descricao_registro(
    registro: dict[str, Any],
    coluna_descricao: str | None,
    coluna_bb_lancamento: str | None,
    coluna_bb_detalhes: str | None,
) -> str:
    lancamento = str(registro.get(coluna_bb_lancamento, "")).strip() if coluna_bb_lancamento else ""
    detalhes = str(registro.get(coluna_bb_detalhes, "")).strip() if coluna_bb_detalhes else ""

    if lancamento and detalhes:
        return f"{lancamento} - {detalhes}"

    if lancamento:
        return lancamento

    if detalhes:
        return detalhes

    if coluna_descricao:
        return str(registro.get(coluna_descricao, "")).strip()

    return "Movimentação sem descrição"


def deve_ignorar_movimentacao(descricao: str) -> bool:
    texto_normal = normalizar_para_comparacao(descricao)
    texto_sem_espacos = re.sub(r"\s+", "", texto_normal)

    termos_ignorar = [
        "SALDO",
        "SALDOANTERIOR",
        "SALDOATUAL",
        "SALDODODIA",
        "SALDODISPONIVEL",
        "SALDOBLOQUEADO",
        "SALDOFINAL",
        "SALDOINICIAL",
    ]

    return any(termo in texto_sem_espacos for termo in termos_ignorar)


def inferir_tipo_por_tipo_lancamento(tipo_lancamento: str, valor: float) -> str | None:
    texto = normalizar_texto(tipo_lancamento).upper()

    if not texto:
        return None

    if "SAIDA" in texto or "SAÍDA" in texto or "DEBITO" in texto or "DÉBITO" in texto:
        return "DESPESA"

    if "ENTRADA" in texto or "CREDITO" in texto or "CRÉDITO" in texto:
        return "RECEITA"

    if "TRANSFERENCIA" in texto or "TRANSFERÊNCIA" in texto:
        return "TRANSFERÊNCIA"

    if valor < 0:
        return "DESPESA"

    if valor > 0:
        return "RECEITA"

    return None


def classificar_movimentacao(
    descricao: str,
    valor: float,
    categoria_banco: str = "",
    tipo_lancamento: str = "",
) -> dict[str, str]:
    descricao_upper = normalizar_para_comparacao(descricao)
    descricao_sem_espacos = re.sub(r"\s+", "", descricao_upper)
    categoria_banco = str(categoria_banco or "").strip()

    for regra in REGRAS_CLASSIFICACAO:
        for termo in regra["termos"]:
            termo_normalizado = normalizar_para_comparacao(termo)
            termo_sem_espacos = re.sub(r"\s+", "", termo_normalizado)

            if termo_normalizado in descricao_upper or termo_sem_espacos in descricao_sem_espacos:
                if regra.get("ignorar"):
                    return {
                        "ignorar": "SIM",
                        "tipo": "",
                        "categoria": "",
                        "subcategoria": "",
                    }

                return {
                    "ignorar": "NAO",
                    "tipo": regra.get("tipo", ""),
                    "categoria": regra.get("categoria", ""),
                    "subcategoria": regra.get("subcategoria", ""),
                }

    tipo_inferido = inferir_tipo_por_tipo_lancamento(tipo_lancamento, valor)

    if categoria_banco:
        return {
            "ignorar": "NAO",
            "tipo": tipo_inferido or ("RECEITA" if valor > 0 else "DESPESA"),
            "categoria": categoria_banco.upper(),
            "subcategoria": "CLASSIFICAÇÃO DO BANCO",
        }

    if tipo_inferido == "TRANSFERÊNCIA":
        return {
            "ignorar": "NAO",
            "tipo": "TRANSFERÊNCIA",
            "categoria": "TRANSFERÊNCIA ENTRE CONTAS",
            "subcategoria": "MOVIMENTAÇÃO ENTRE CONTAS",
        }

    if tipo_inferido == "RECEITA" or valor > 0:
        return {
            "ignorar": "NAO",
            "tipo": "RECEITA",
            "categoria": "OUTRAS RECEITAS",
            "subcategoria": "DIVERSOS",
        }

    return {
        "ignorar": "NAO",
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

    colunas = detectar_colunas(registros)

    movimentacoes = []

    for indice, registro in enumerate(registros, start=1):
        data = str(registro.get(colunas["data"], "")).strip() if colunas["data"] else ""

        descricao = montar_descricao_registro(
            registro=registro,
            coluna_descricao=colunas["descricao"],
            coluna_bb_lancamento=colunas["bb_lancamento"],
            coluna_bb_detalhes=colunas["bb_detalhes"],
        )

        valor = obter_valor_registro(registro, colunas["valor"])

        categoria_banco = (
            str(registro.get(colunas["categoria_banco"], "")).strip()
            if colunas["categoria_banco"]
            else ""
        )

        tipo_lancamento = (
            str(registro.get(colunas["tipo_lancamento"], "")).strip()
            if colunas["tipo_lancamento"]
            else ""
        )

        if not descricao and valor == 0:
            continue

        if deve_ignorar_movimentacao(descricao):
            continue

        classificacao = classificar_movimentacao(
            descricao=descricao,
            valor=valor,
            categoria_banco=categoria_banco,
            tipo_lancamento=tipo_lancamento,
        )

        if classificacao.get("ignorar") == "SIM":
            continue

        tipo = classificacao["tipo"]
        situacao = "PAGO"

        if tipo == "RECEITA":
            situacao = "RECEBIDO"
        elif tipo == "TRANSFERÊNCIA":
            situacao = "PAGO"

        observacao = f"Importado do extrato: {caminho.name}"

        if categoria_banco:
            observacao += f". Categoria banco: {categoria_banco}"

        if tipo_lancamento:
            observacao += f". Tipo lançamento banco: {tipo_lancamento}"

        movimentacoes.append(
            {
                "indice": len(movimentacoes),
                "linha_original": indice,
                "data": data,
                "descricao": descricao or "Movimentação sem descrição",
                "valor": valor,
                "valor_fmt": valor_para_texto_brasil(valor),
                "tipo": tipo,
                "categoria": classificacao["categoria"],
                "subcategoria": classificacao["subcategoria"],
                "situacao": situacao,
                "forma_pagamento": "CONTA",
                "conta": "BANCO PRINCIPAL",
                "observacao": observacao,
            }
        )

    return {
        "movimentacoes": movimentacoes,
        "colunas_detectadas": {
            "data": colunas["data"],
            "descricao": colunas["descricao"],
            "valor": colunas["valor"],
            "categoria_banco": colunas["categoria_banco"],
            "tipo_lancamento": colunas["tipo_lancamento"],
            "bb_lancamento": colunas["bb_lancamento"],
            "bb_detalhes": colunas["bb_detalhes"],
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