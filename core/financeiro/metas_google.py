from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
import uuid


ABA_METAS_FINANCEIRAS = "METAS_FINANCEIRAS"


CABECALHO_METAS = [
    "ID",
    "DATA_CADASTRO",
    "NOME_META",
    "CATEGORIA",
    "VALOR_ALVO",
    "VALOR_ATUAL",
    "DATA_ALVO",
    "PRIORIDADE",
    "STATUS",
    "OBSERVACAO",
]


CATEGORIAS_METAS = [
    "Reserva de Emergência",
    "Viagem",
    "Imóvel",
    "Veículo",
    "Educação",
    "Aposentadoria",
    "Investimento",
    "Quitação de Dívida",
    "Outros",
]


PRIORIDADES_METAS = [
    "Alta",
    "Média",
    "Baixa",
]


STATUS_METAS = [
    "Em andamento",
    "Concluída",
    "Pausada",
    "Cancelada",
]


def obter_planilha_por_link(link_planilha: str):
    """
    Abre a planilha pelo link configurado no sistema.
    Usa o mesmo padrão de autenticação já utilizado nos módulos financeiros.
    """

    try:
        import os

        import gspread
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = None

        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json",
                    scopes,
                )
                creds = flow.run_local_server(port=0)

            with open("token.json", "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        cliente = gspread.authorize(creds)

        spreadsheet_id = extrair_id_planilha(link_planilha)

        return cliente.open_by_key(spreadsheet_id)

    except Exception as erro:
        raise RuntimeError(
            f"Não foi possível abrir a planilha de metas financeiras: {erro}"
        ) from erro


def extrair_id_planilha(link_planilha: str) -> str:
    """
    Extrai o ID da planilha a partir de um link do Google Sheets
    ou aceita diretamente o ID.
    """

    if not link_planilha:
        raise ValueError("Link da planilha não informado.")

    texto = str(link_planilha).strip()

    if "/spreadsheets/d/" in texto:
        parte = texto.split("/spreadsheets/d/", 1)[1]
        return parte.split("/", 1)[0].split("?", 1)[0].strip()

    return texto


def normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""

    texto = str(valor).strip().upper()

    trocas = {
        "Á": "A",
        "À": "A",
        "Ã": "A",
        "Â": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)

    return texto


def converter_valor(valor: Any) -> float:
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
        .replace("\u00a0", "")
        .strip()
    )

    negativo = False

    if texto.startswith("(") and texto.endswith(")"):
        negativo = True
        texto = texto.replace("(", "").replace(")", "")

    if texto.startswith("-"):
        negativo = True
        texto = texto.replace("-", "", 1)

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        numero = float(texto)
    except Exception:
        return 0.0

    if negativo:
        numero = numero * -1

    return numero


def formatar_moeda(valor: Any) -> str:
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0

    texto = f"R$ {numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor: Any) -> str:
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0

    return f"{numero:.1f}%".replace(".", ",")


def obter_aba_metas(planilha):
    """
    Obtém ou cria a aba METAS_FINANCEIRAS.
    """

    try:
        aba = planilha.worksheet(ABA_METAS_FINANCEIRAS)
    except Exception:
        aba = planilha.add_worksheet(
            title=ABA_METAS_FINANCEIRAS,
            rows=1000,
            cols=len(CABECALHO_METAS) + 5,
        )

    valores = aba.get_all_values()

    if not valores:
        aba.update("A1:J1", [CABECALHO_METAS])
        formatar_aba_metas(aba)
    else:
        cabecalho_atual = valores[0]

        if cabecalho_atual[: len(CABECALHO_METAS)] != CABECALHO_METAS:
            aba.update("A1:J1", [CABECALHO_METAS])
            formatar_aba_metas(aba)

    return aba


def formatar_aba_metas(aba) -> None:
    """
    Aplica formatação simples e segura na aba de metas.
    """

    try:
        aba.freeze(rows=1)
    except Exception:
        pass

    try:
        aba.format(
            "A1:J1",
            {
                "backgroundColor": {"red": 0.12, "green": 0.25, "blue": 0.52},
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            },
        )

        aba.format(
            "A:J",
            {
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
            },
        )

        aba.format(
            "E:F",
            {
                "numberFormat": {
                    "type": "CURRENCY",
                    "pattern": "R$ #,##0.00",
                }
            },
        )

        aba.columns_auto_resize(0, 10)
    except Exception:
        pass


def calcular_meses_restantes(data_alvo: str) -> int:
    if not data_alvo:
        return 0

    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
    ]

    alvo = None

    for formato in formatos:
        try:
            alvo = datetime.strptime(str(data_alvo).strip()[:10], formato).date()
            break
        except Exception:
            continue

    if not alvo:
        return 0

    hoje = date.today()

    meses = (alvo.year - hoje.year) * 12 + (alvo.month - hoje.month)

    if alvo.day > hoje.day:
        meses += 1

    return max(meses, 0)


def calcular_dados_meta(meta: dict) -> dict:
    valor_alvo = converter_valor(meta.get("VALOR_ALVO"))
    valor_atual = converter_valor(meta.get("VALOR_ATUAL"))
    falta = max(valor_alvo - valor_atual, 0)

    percentual = 0.0
    if valor_alvo > 0:
        percentual = min((valor_atual / valor_alvo) * 100, 100)

    meses_restantes = calcular_meses_restantes(meta.get("DATA_ALVO", ""))

    aporte_mensal = 0.0
    if meses_restantes > 0:
        aporte_mensal = falta / meses_restantes

    status = str(meta.get("STATUS", "")).strip() or "Em andamento"

    if valor_alvo > 0 and valor_atual >= valor_alvo:
        situacao_calculada = "Meta atingida"
        classe = "green"
    elif status in {"Concluída", "Cancelada"}:
        situacao_calculada = status
        classe = "green" if status == "Concluída" else "red"
    elif meses_restantes == 0 and falta > 0:
        situacao_calculada = "Prazo vencido ou sem prazo"
        classe = "red"
    elif percentual >= 75:
        situacao_calculada = "Bem encaminhada"
        classe = "green"
    elif percentual >= 40:
        situacao_calculada = "Em evolução"
        classe = "amber"
    else:
        situacao_calculada = "Precisa de atenção"
        classe = "red"

    meta_formatada = dict(meta)

    meta_formatada.update(
        {
            "valor_alvo": valor_alvo,
            "valor_alvo_fmt": formatar_moeda(valor_alvo),
            "valor_atual": valor_atual,
            "valor_atual_fmt": formatar_moeda(valor_atual),
            "valor_faltante": falta,
            "valor_faltante_fmt": formatar_moeda(falta),
            "percentual": percentual,
            "percentual_fmt": formatar_percentual(percentual),
            "meses_restantes": meses_restantes,
            "aporte_mensal": aporte_mensal,
            "aporte_mensal_fmt": formatar_moeda(aporte_mensal),
            "situacao_calculada": situacao_calculada,
            "classe": classe,
        }
    )

    return meta_formatada


def listar_metas_financeiras(link_planilha: str) -> dict:
    planilha = obter_planilha_por_link(link_planilha)
    aba = obter_aba_metas(planilha)

    registros = aba.get_all_records()

    metas = []

    for linha in registros:
        if not linha.get("ID") and not linha.get("NOME_META"):
            continue

        metas.append(calcular_dados_meta(linha))

    total_alvo = sum(meta["valor_alvo"] for meta in metas)
    total_atual = sum(meta["valor_atual"] for meta in metas)
    total_faltante = max(total_alvo - total_atual, 0)

    percentual_geral = 0.0
    if total_alvo > 0:
        percentual_geral = min(total_atual / total_alvo * 100, 100)

    metas_ativas = [
        meta
        for meta in metas
        if normalizar_texto(meta.get("STATUS")) not in {"CONCLUIDA", "CANCELADA"}
    ]

    metas_concluidas = [
        meta
        for meta in metas
        if normalizar_texto(meta.get("STATUS")) == "CONCLUIDA"
        or meta.get("situacao_calculada") == "Meta atingida"
    ]

    metas_atencao = [
        meta
        for meta in metas
        if meta.get("classe") == "red"
        and normalizar_texto(meta.get("STATUS")) not in {"CANCELADA", "CONCLUIDA"}
    ]

    return {
        "metas": metas,
        "total_metas": len(metas),
        "total_ativas": len(metas_ativas),
        "total_concluidas": len(metas_concluidas),
        "total_atencao": len(metas_atencao),
        "total_alvo": total_alvo,
        "total_alvo_fmt": formatar_moeda(total_alvo),
        "total_atual": total_atual,
        "total_atual_fmt": formatar_moeda(total_atual),
        "total_faltante": total_faltante,
        "total_faltante_fmt": formatar_moeda(total_faltante),
        "percentual_geral": percentual_geral,
        "percentual_geral_fmt": formatar_percentual(percentual_geral),
    }


def salvar_meta_financeira(
    link_planilha: str,
    dados: dict,
) -> dict:
    planilha = obter_planilha_por_link(link_planilha)
    aba = obter_aba_metas(planilha)

    meta_id = str(uuid.uuid4())[:8].upper()

    linha = [
        meta_id,
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        str(dados.get("nome_meta", "")).strip(),
        str(dados.get("categoria", "")).strip(),
        converter_valor(dados.get("valor_alvo")),
        converter_valor(dados.get("valor_atual")),
        str(dados.get("data_alvo", "")).strip(),
        str(dados.get("prioridade", "")).strip(),
        str(dados.get("status", "")).strip(),
        str(dados.get("observacao", "")).strip(),
    ]

    aba.append_row(linha, value_input_option="USER_ENTERED")

    try:
        formatar_aba_metas(aba)
    except Exception:
        pass

    return {
        "ok": True,
        "id": meta_id,
        "mensagem": "Meta financeira salva com sucesso.",
        "url": planilha.url,
    }


def atualizar_meta_financeira(
    link_planilha: str,
    meta_id: str,
    dados: dict,
) -> dict:
    planilha = obter_planilha_por_link(link_planilha)
    aba = obter_aba_metas(planilha)

    registros = aba.get_all_records()

    linha_encontrada = None

    for indice, linha in enumerate(registros, start=2):
        if str(linha.get("ID", "")).strip() == str(meta_id).strip():
            linha_encontrada = indice
            break

    if not linha_encontrada:
        raise ValueError(f"Meta não localizada: {meta_id}")

    nova_linha = [
        meta_id,
        dados.get("data_cadastro", ""),
        str(dados.get("nome_meta", "")).strip(),
        str(dados.get("categoria", "")).strip(),
        converter_valor(dados.get("valor_alvo")),
        converter_valor(dados.get("valor_atual")),
        str(dados.get("data_alvo", "")).strip(),
        str(dados.get("prioridade", "")).strip(),
        str(dados.get("status", "")).strip(),
        str(dados.get("observacao", "")).strip(),
    ]

    aba.update(f"A{linha_encontrada}:J{linha_encontrada}", [nova_linha])

    try:
        formatar_aba_metas(aba)
    except Exception:
        pass

    return {
        "ok": True,
        "id": meta_id,
        "mensagem": "Meta financeira atualizada com sucesso.",
        "url": planilha.url,
    }


def excluir_meta_financeira(
    link_planilha: str,
    meta_id: str,
) -> dict:
    planilha = obter_planilha_por_link(link_planilha)
    aba = obter_aba_metas(planilha)

    registros = aba.get_all_records()

    linha_encontrada = None

    for indice, linha in enumerate(registros, start=2):
        if str(linha.get("ID", "")).strip() == str(meta_id).strip():
            linha_encontrada = indice
            break

    if not linha_encontrada:
        raise ValueError(f"Meta não localizada: {meta_id}")

    aba.delete_rows(linha_encontrada)

    return {
        "ok": True,
        "id": meta_id,
        "mensagem": "Meta financeira excluída com sucesso.",
        "url": planilha.url,
    }


def tentar_converter_data(valor: Any) -> date | None:
    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    texto = texto[:10]

    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d-%m-%Y",
        "%d-%m-%y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except Exception:
            continue

    return None


def ultimo_dia_mes(data_base: date) -> date:
    if data_base.month == 12:
        return date(data_base.year, 12, 31)

    primeiro_proximo_mes = date(data_base.year, data_base.month + 1, 1)
    return primeiro_proximo_mes - timedelta(days=1)


def data_alvo_em_meses(quantidade_meses: int) -> str:
    hoje = date.today()

    mes = hoje.month + quantidade_meses
    ano = hoje.year + ((mes - 1) // 12)
    mes = ((mes - 1) % 12) + 1

    dia = min(hoje.day, ultimo_dia_mes(date(ano, mes, 1)).day)

    return date(ano, mes, dia).strftime("%Y-%m-%d")


def localizar_coluna(cabecalhos: list[str], opcoes: list[str]) -> str | None:
    cabecalhos_normalizados = {
        normalizar_texto(cabecalho): cabecalho
        for cabecalho in cabecalhos
    }

    for opcao in opcoes:
        opcao_norm = normalizar_texto(opcao)

        if opcao_norm in cabecalhos_normalizados:
            return cabecalhos_normalizados[opcao_norm]

    for cabecalho_norm, cabecalho_original in cabecalhos_normalizados.items():
        for opcao in opcoes:
            opcao_norm = normalizar_texto(opcao)

            if opcao_norm in cabecalho_norm:
                return cabecalho_original

    return None


def obter_registros_seguros(aba) -> list[dict]:
    try:
        return aba.get_all_records()
    except Exception:
        return []


def aba_parece_movimentacao(titulo: str) -> bool:
    titulo_norm = normalizar_texto(titulo)

    palavras = [
        "LANCAMENTO",
        "LANCAMENTOS",
        "BASE",
        "EXTRATO",
        "EXTRATOS",
        "MOVIMENTO",
        "MOVIMENTACAO",
        "MOVIMENTACOES",
        "RECEITA",
        "RECEITAS",
        "DESPESA",
        "DESPESAS",
    ]

    return any(palavra in titulo_norm for palavra in palavras)


def aba_parece_patrimonio(titulo: str) -> bool:
    """
    Identifica somente abas claramente patrimoniais.

    Não inclui INVESTIMENTOS, CARTEIRA, ATIVOS ou BENS para evitar
    somar dados duplicados ou usar valores que não representam
    o patrimônio líquido consolidado.
    """

    titulo_norm = normalizar_texto(titulo)

    palavras = [
        "PATRIMONIO",
        "PATRIMONIAL",
    ]

    return any(palavra in titulo_norm for palavra in palavras)


def linha_patrimonial_totalizadora(linha: dict) -> bool:
    """
    Retorna True quando a linha parece ser uma linha de totalização/resumo.

    Isso evita somar o total junto com os itens individuais de patrimônio.
    """

    texto_linha = " ".join(
        normalizar_texto(valor_linha)
        for valor_linha in linha.values()
    )

    palavras_totalizadoras = [
        "TOTAL",
        "TOTAL GERAL",
        "SUBTOTAL",
        "RESUMO",
        "CONSOLIDADO",
        "PATRIMONIO TOTAL",
        "PATRIMONIO LIQUIDO",
        "SALDO TOTAL",
    ]

    return any(palavra in texto_linha for palavra in palavras_totalizadoras)


def classificar_lancamento(
    titulo_aba: str,
    linha: dict,
    coluna_tipo: str | None,
    coluna_categoria: str | None,
    valor: float,
) -> str | None:
    titulo_norm = normalizar_texto(titulo_aba)

    textos = []

    if coluna_tipo:
        textos.append(normalizar_texto(linha.get(coluna_tipo)))

    if coluna_categoria:
        textos.append(normalizar_texto(linha.get(coluna_categoria)))

    texto_completo = " ".join(textos)

    if valor < 0:
        return "despesa"

    if "RECEITA" in texto_completo or "ENTRADA" in texto_completo:
        return "receita"

    if (
        "DESPESA" in texto_completo
        or "SAIDA" in texto_completo
        or "GASTO" in texto_completo
        or "PAGAMENTO" in texto_completo
    ):
        return "despesa"

    if "RECEITA" in titulo_norm:
        return "receita"

    if "DESPESA" in titulo_norm:
        return "despesa"

    return None


def analisar_receitas_despesas(planilha) -> dict:
    """
    Analisa abas de lançamentos/extratos/receitas/despesas.

    Retorna totais, médias formatadas e diagnóstico detalhado
    para exibição na tela de metas.
    """

    total_receitas = 0.0
    total_despesas = 0.0
    meses_encontrados: set[str] = set()
    linhas_utilizadas = 0
    detalhes_abas = []

    limite_data = date.today() - timedelta(days=120)

    for aba in planilha.worksheets():
        if normalizar_texto(aba.title) == normalizar_texto(ABA_METAS_FINANCEIRAS):
            continue

        if not aba_parece_movimentacao(aba.title):
            continue

        registros = obter_registros_seguros(aba)

        detalhe_aba = {
            "aba": aba.title,
            "coluna_valor": "",
            "coluna_tipo": "",
            "coluna_categoria": "",
            "coluna_data": "",
            "linhas_utilizadas": 0,
            "receitas_aba": 0.0,
            "despesas_aba": 0.0,
            "receitas_aba_fmt": "R$ 0,00",
            "despesas_aba_fmt": "R$ 0,00",
            "mensagem": "",
        }

        if not registros:
            detalhe_aba["mensagem"] = "Aba sem registros."
            detalhes_abas.append(detalhe_aba)
            continue

        cabecalhos = list(registros[0].keys())

        coluna_valor = localizar_coluna(
            cabecalhos,
            [
                "VALOR",
                "VALOR_TOTAL",
                "VALOR TOTAL",
                "VALOR_PAGO",
                "VALOR PAGO",
                "VALOR_LANCAMENTO",
                "VALOR LANÇAMENTO",
                "VALOR LANCAMENTO",
                "TOTAL",
            ],
        )

        coluna_tipo = localizar_coluna(
            cabecalhos,
            [
                "TIPO",
                "TIPO_LANCAMENTO",
                "TIPO LANÇAMENTO",
                "TIPO LANCAMENTO",
                "NATUREZA",
                "RECEITA_DESPESA",
                "ENTRADA_SAIDA",
            ],
        )

        coluna_categoria = localizar_coluna(
            cabecalhos,
            [
                "CATEGORIA",
                "GRUPO",
                "CLASSIFICACAO",
                "CLASSIFICAÇÃO",
                "DESCRICAO",
                "DESCRIÇÃO",
            ],
        )

        coluna_data = localizar_coluna(
            cabecalhos,
            [
                "DATA",
                "DATA_LANCAMENTO",
                "DATA LANÇAMENTO",
                "DATA LANCAMENTO",
                "DATA_PAGAMENTO",
                "DATA PAGAMENTO",
                "COMPETENCIA",
                "COMPETÊNCIA",
                "MES",
                "MÊS",
            ],
        )

        detalhe_aba["coluna_valor"] = coluna_valor or ""
        detalhe_aba["coluna_tipo"] = coluna_tipo or ""
        detalhe_aba["coluna_categoria"] = coluna_categoria or ""
        detalhe_aba["coluna_data"] = coluna_data or ""

        if not coluna_valor:
            detalhe_aba["mensagem"] = "Nenhuma coluna de valor foi localizada."
            detalhes_abas.append(detalhe_aba)
            continue

        receitas_aba = 0.0
        despesas_aba = 0.0
        linhas_aba = 0

        for linha in registros:
            valor = converter_valor(linha.get(coluna_valor))

            if valor == 0:
                continue

            data_lancamento = None

            if coluna_data:
                data_lancamento = tentar_converter_data(linha.get(coluna_data))

            if data_lancamento and data_lancamento < limite_data:
                continue

            if data_lancamento:
                meses_encontrados.add(
                    f"{data_lancamento.year}-{data_lancamento.month:02d}"
                )

            classificacao = classificar_lancamento(
                titulo_aba=aba.title,
                linha=linha,
                coluna_tipo=coluna_tipo,
                coluna_categoria=coluna_categoria,
                valor=valor,
            )

            if classificacao == "receita":
                total_receitas += abs(valor)
                receitas_aba += abs(valor)
                linhas_utilizadas += 1
                linhas_aba += 1

            elif classificacao == "despesa":
                total_despesas += abs(valor)
                despesas_aba += abs(valor)
                linhas_utilizadas += 1
                linhas_aba += 1

        detalhe_aba["linhas_utilizadas"] = linhas_aba
        detalhe_aba["receitas_aba"] = receitas_aba
        detalhe_aba["despesas_aba"] = despesas_aba
        detalhe_aba["receitas_aba_fmt"] = formatar_moeda(receitas_aba)
        detalhe_aba["despesas_aba_fmt"] = formatar_moeda(despesas_aba)

        if linhas_aba == 0:
            detalhe_aba["mensagem"] = "Nenhuma linha foi classificada como receita ou despesa."
        else:
            detalhe_aba["mensagem"] = "Linhas consideradas no cálculo de fluxo financeiro."

        detalhes_abas.append(detalhe_aba)

    quantidade_meses = max(len(meses_encontrados), 1)

    media_receitas = total_receitas / quantidade_meses
    media_despesas = total_despesas / quantidade_meses
    saldo_medio = media_receitas - media_despesas

    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "media_receitas": media_receitas,
        "media_despesas": media_despesas,
        "saldo_medio": saldo_medio,
        "total_receitas_fmt": formatar_moeda(total_receitas),
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "media_receitas_fmt": formatar_moeda(media_receitas),
        "media_despesas_fmt": formatar_moeda(media_despesas),
        "saldo_medio_fmt": formatar_moeda(saldo_medio),
        "quantidade_meses": quantidade_meses,
        "linhas_utilizadas": linhas_utilizadas,
        "detalhes_abas": detalhes_abas,
    }


def analisar_patrimonio(planilha) -> dict:
    """
    Calcula o patrimônio somente a partir de abas cujo nome contenha
    PATRIMONIO ou PATRIMONIAL.

    Ignora linhas totalizadoras para evitar somar totais junto com itens.
    Também retorna diagnóstico detalhado para exibir na tela.
    """

    patrimonio_total = 0.0
    linhas_utilizadas = 0
    detalhes_abas = []

    for aba in planilha.worksheets():
        if normalizar_texto(aba.title) == normalizar_texto(ABA_METAS_FINANCEIRAS):
            continue

        if not aba_parece_patrimonio(aba.title):
            continue

        registros = obter_registros_seguros(aba)

        detalhe_aba = {
            "aba": aba.title,
            "foi_analisada": True,
            "coluna_valor": "",
            "coluna_tipo": "",
            "linhas_utilizadas": 0,
            "linhas_ignoradas": 0,
            "total_aba": 0.0,
            "total_aba_fmt": "R$ 0,00",
            "valores_considerados": [],
            "valores_ignorados": [],
            "mensagem": "",
        }

        if not registros:
            detalhe_aba["mensagem"] = "Aba sem registros."
            detalhes_abas.append(detalhe_aba)
            continue

        cabecalhos = list(registros[0].keys())

        coluna_valor = localizar_coluna(
            cabecalhos,
            [
                "PATRIMONIO_LIQUIDO",
                "PATRIMÔNIO LÍQUIDO",
                "PATRIMONIO LIQUIDO",
                "VALOR_ATUAL",
                "VALOR ATUAL",
                "SALDO",
                "SALDO_ATUAL",
                "SALDO ATUAL",
                "PATRIMONIO",
                "PATRIMÔNIO",
                "VALOR",
                "TOTAL",
            ],
        )

        coluna_tipo = localizar_coluna(
            cabecalhos,
            [
                "TIPO",
                "CATEGORIA",
                "GRUPO",
                "NATUREZA",
                "CLASSIFICACAO",
                "CLASSIFICAÇÃO",
            ],
        )

        detalhe_aba["coluna_valor"] = coluna_valor or ""
        detalhe_aba["coluna_tipo"] = coluna_tipo or ""

        if not coluna_valor:
            detalhe_aba["mensagem"] = "Nenhuma coluna de valor foi localizada."
            detalhes_abas.append(detalhe_aba)
            continue

        total_aba = 0.0
        linhas_aba = 0
        linhas_ignoradas = 0
        valores_considerados = []
        valores_ignorados = []

        for linha in registros:
            valor_original = linha.get(coluna_valor)

            if linha_patrimonial_totalizadora(linha):
                valor_ignorado = converter_valor(valor_original)
                linhas_ignoradas += 1

                if len(valores_ignorados) < 12:
                    valores_ignorados.append(
                        {
                            "valor_original": str(valor_original),
                            "valor_convertido_fmt": formatar_moeda(valor_ignorado),
                            "motivo": "Linha ignorada por conter TOTAL/SUBTOTAL/RESUMO/CONSOLIDADO.",
                        }
                    )

                continue

            valor = converter_valor(valor_original)

            if valor == 0:
                continue

            tipo_norm = normalizar_texto(linha.get(coluna_tipo)) if coluna_tipo else ""

            if any(
                palavra in tipo_norm
                for palavra in ["DIVIDA", "DÍVIDA", "PASSIVO", "FINANCIAMENTO"]
            ):
                valor_final = abs(valor) * -1
            else:
                valor_final = valor

            patrimonio_total += valor_final
            total_aba += valor_final
            linhas_utilizadas += 1
            linhas_aba += 1

            if len(valores_considerados) < 12:
                valores_considerados.append(
                    {
                        "valor_original": str(valor_original),
                        "valor_convertido": valor_final,
                        "valor_convertido_fmt": formatar_moeda(valor_final),
                        "tipo": str(linha.get(coluna_tipo, "")) if coluna_tipo else "",
                    }
                )

        detalhe_aba["linhas_utilizadas"] = linhas_aba
        detalhe_aba["linhas_ignoradas"] = linhas_ignoradas
        detalhe_aba["total_aba"] = total_aba
        detalhe_aba["total_aba_fmt"] = formatar_moeda(total_aba)
        detalhe_aba["valores_considerados"] = valores_considerados
        detalhe_aba["valores_ignorados"] = valores_ignorados

        if linhas_aba == 0 and linhas_ignoradas > 0:
            detalhe_aba["mensagem"] = (
                "Somente linhas totalizadoras foram encontradas e ignoradas."
            )
        elif linhas_aba == 0:
            detalhe_aba["mensagem"] = "Nenhum valor aproveitável foi encontrado."
        elif linhas_ignoradas > 0:
            detalhe_aba["mensagem"] = (
                "Valores considerados no cálculo patrimonial. "
                "Linhas totalizadoras foram ignoradas."
            )
        else:
            detalhe_aba["mensagem"] = "Valores considerados no cálculo patrimonial."

        detalhes_abas.append(detalhe_aba)

    return {
        "patrimonio_total": patrimonio_total,
        "patrimonio_total_fmt": formatar_moeda(patrimonio_total),
        "linhas_utilizadas": linhas_utilizadas,
        "detalhes_abas": detalhes_abas,
    }


def meta_ja_existe(nome_meta: str, metas_existentes: list[dict]) -> bool:
    nome_norm = normalizar_texto(nome_meta)

    for meta in metas_existentes:
        nome_existente = normalizar_texto(meta.get("NOME_META"))

        if nome_existente == nome_norm:
            return True

    return False


def montar_sugestoes_metas(
    dados_fluxo: dict,
    dados_patrimonio: dict,
) -> list[dict]:
    media_receitas = float(dados_fluxo.get("media_receitas") or 0)
    media_despesas = float(dados_fluxo.get("media_despesas") or 0)
    saldo_medio = float(dados_fluxo.get("saldo_medio") or 0)
    patrimonio_total = float(dados_patrimonio.get("patrimonio_total") or 0)
    linhas_patrimonio = int(dados_patrimonio.get("linhas_utilizadas") or 0)

    sugestoes = []

    if media_despesas > 0:
        sugestoes.append(
            {
                "nome_meta": "Reserva de emergência de 3 meses",
                "categoria": "Reserva de Emergência",
                "valor_alvo": round(media_despesas * 3, 2),
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(12),
                "prioridade": "Alta",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente com base na média de despesas. "
                    f"Despesa média estimada: {formatar_moeda(media_despesas)}."
                ),
            }
        )

    if saldo_medio > 0:
        sugestoes.append(
            {
                "nome_meta": "Investimento mensal programado",
                "categoria": "Investimento",
                "valor_alvo": round(saldo_medio * 6, 2),
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(6),
                "prioridade": "Média",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente com base no saldo médio positivo. "
                    f"Saldo médio estimado: {formatar_moeda(saldo_medio)}."
                ),
            }
        )

        sugestoes.append(
            {
                "nome_meta": "Economizar 10% da renda mensal",
                "categoria": "Investimento",
                "valor_alvo": round(media_receitas * 0.10 * 6, 2),
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(6),
                "prioridade": "Média",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente para criar disciplina de economia. "
                    f"Receita média estimada: {formatar_moeda(media_receitas)}."
                ),
            }
        )

    if media_despesas > 0:
        sugestoes.append(
            {
                "nome_meta": "Reduzir despesas variáveis em 10%",
                "categoria": "Outros",
                "valor_alvo": round(media_despesas * 0.10 * 6, 2),
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(6),
                "prioridade": "Alta",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente para reduzir gastos. "
                    f"Economia estimada em 6 meses: {formatar_moeda(media_despesas * 0.10 * 6)}."
                ),
            }
        )

    if patrimonio_total > 0 and linhas_patrimonio > 0:
        sugestoes.append(
            {
                "nome_meta": "Aumentar patrimônio líquido em 10%",
                "categoria": "Investimento",
                "valor_alvo": round(patrimonio_total * 1.10, 2),
                "valor_atual": round(patrimonio_total, 2),
                "data_alvo": data_alvo_em_meses(12),
                "prioridade": "Média",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente somente com base em aba patrimonial. "
                    f"Patrimônio líquido estimado: {formatar_moeda(patrimonio_total)}."
                ),
            }
        )

    if not sugestoes:
        sugestoes.append(
            {
                "nome_meta": "Organizar primeira reserva financeira",
                "categoria": "Reserva de Emergência",
                "valor_alvo": 1000,
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(6),
                "prioridade": "Alta",
                "status": "Em andamento",
                "observacao": (
                    "Meta inicial sugerida automaticamente. "
                    "Não foram encontrados dados suficientes de receitas, despesas ou patrimônio."
                ),
            }
        )

    sugestoes_validas = []

    for sugestao in sugestoes:
        if converter_valor(sugestao.get("valor_alvo")) <= 0:
            continue

        sugestoes_validas.append(sugestao)

    return sugestoes_validas


def sugerir_metas_automaticas(link_planilha: str) -> dict:
    """
    Analisa receitas, despesas e patrimônio para sugerir metas financeiras.

    Regras:
    - não duplica meta com o mesmo nome;
    - não usa abas de investimentos como patrimônio líquido;
    - ignora linhas totalizadoras no patrimônio;
    - retorna diagnóstico para a tela;
    - se não encontrar dados suficientes, cria uma meta inicial básica.
    """

    planilha = obter_planilha_por_link(link_planilha)
    obter_aba_metas(planilha)

    resumo_atual = listar_metas_financeiras(link_planilha)
    metas_existentes = resumo_atual.get("metas", [])

    dados_fluxo = analisar_receitas_despesas(planilha)
    dados_patrimonio = analisar_patrimonio(planilha)

    sugestoes = montar_sugestoes_metas(
        dados_fluxo=dados_fluxo,
        dados_patrimonio=dados_patrimonio,
    )

    metas_cadastradas = []
    metas_ignoradas = []

    for sugestao in sugestoes:
        if meta_ja_existe(sugestao["nome_meta"], metas_existentes):
            metas_ignoradas.append(sugestao)
            continue

        resultado = salvar_meta_financeira(
            link_planilha=link_planilha,
            dados=sugestao,
        )

        metas_cadastradas.append(
            {
                **sugestao,
                "id": resultado.get("id"),
            }
        )

    return {
        "ok": True,
        "quantidade_cadastrada": len(metas_cadastradas),
        "quantidade_ignorada": len(metas_ignoradas),
        "metas_cadastradas": metas_cadastradas,
        "metas_ignoradas": metas_ignoradas,
        "dados_fluxo": dados_fluxo,
        "dados_patrimonio": dados_patrimonio,
        "url": planilha.url,
    }