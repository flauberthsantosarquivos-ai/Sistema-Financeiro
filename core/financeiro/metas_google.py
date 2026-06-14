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

    Esta versão é mais robusta porque:
    - valida se o link/ID veio vazio;
    - aceita link completo ou ID da planilha;
    - tenta abrir por URL e por ID;
    - usa token.json/credentials.json do mesmo projeto;
    - devolve mensagem de erro mais clara para a tela de Metas.
    """

    texto_link = str(link_planilha or "").strip().strip('"').strip("'").strip()
    texto_link = texto_link.rstrip(" .,;\n\r\t/")

    if not texto_link:
        raise RuntimeError(
            "Nenhuma planilha foi informada para o módulo de metas. "
            "Verifique em Configurações se a Central Financeira possui uma planilha Google vinculada."
        )

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
        token_path = "token.json"
        credentials_path = "credentials.json"

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise RuntimeError(
                        "Arquivo credentials.json não encontrado na pasta do projeto."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path,
                    scopes,
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        cliente = gspread.authorize(creds)
        spreadsheet_id = extrair_id_planilha(texto_link)

        erros_tentativas = []

        if "docs.google.com/spreadsheets" in texto_link:
            try:
                return cliente.open_by_url(texto_link)
            except Exception as erro_url:
                erros_tentativas.append(f"open_by_url: {erro_url}")

        try:
            return cliente.open_by_key(spreadsheet_id)
        except Exception as erro_key:
            erros_tentativas.append(f"open_by_key: {erro_key}")

        try:
            return cliente.open(spreadsheet_id)
        except Exception as erro_nome:
            erros_tentativas.append(f"open por nome/ID: {erro_nome}")

        raise RuntimeError(
            "Não foi possível abrir a planilha informada. "
            f"ID extraído: {spreadsheet_id}. "
            f"Tentativas: {' | '.join(erros_tentativas)}"
        )

    except Exception as erro:
        raise RuntimeError(
            "Não foi possível abrir a planilha de metas financeiras. "
            f"Link/ID recebido: {texto_link}. "
            f"Detalhe técnico: {erro}"
        ) from erro


def extrair_id_planilha(link_planilha: str) -> str:
    """
    Extrai o ID da planilha a partir de um link do Google Sheets
    ou aceita diretamente o ID.

    Também remove pontuação acidental no fim do texto, como ponto final,
    vírgula ou barra, comum quando o link é copiado de uma mensagem.
    """

    if not link_planilha:
        raise ValueError("Link da planilha não informado.")

    texto = str(link_planilha).strip().strip('"').strip("'").strip()

    # Remove caracteres acidentais no fim do link/ID.
    # Exemplo: .../1ABCDEF.  ->  .../1ABCDEF
    texto = texto.rstrip(" .,;\n\r\t/")

    if "/spreadsheets/d/" in texto:
        parte = texto.split("/spreadsheets/d/", 1)[1]
        spreadsheet_id = (
            parte
            .split("/", 1)[0]
            .split("?", 1)[0]
            .split("#", 1)[0]
            .strip()
            .rstrip(" .,;\n\r\t/")
        )
    else:
        spreadsheet_id = (
            texto
            .split("?", 1)[0]
            .split("#", 1)[0]
            .strip()
            .rstrip(" .,;\n\r\t/")
        )

    if not spreadsheet_id:
        raise ValueError(
            "Não foi possível extrair o ID da planilha a partir do link informado."
        )

    return spreadsheet_id


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

    Ponto importante:
    - Não força o cabeçalho quando a aba já possui os campos essenciais.
    - Isso evita desalinhamento quando a planilha já existe ou foi criada em
      versão anterior com pequenas diferenças.
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
        return aba

    cabecalho_atual = valores[0]

    # Se a aba já possui os campos essenciais, não sobrescreve o cabeçalho.
    # Sobrescrever cabeçalho em aba existente pode deslocar a interpretação dos
    # campos e fazer VALOR_ATUAL aparecer como zero na tela.
    campos_essenciais = {
        "NOME_META",
        "CATEGORIA",
        "VALOR_ALVO",
        "VALOR_ATUAL",
    }

    campos_atuais = {
        normalizar_texto(campo)
        for campo in cabecalho_atual
        if str(campo or "").strip()
    }

    if campos_essenciais.issubset(campos_atuais):
        return aba

    # Só recria o cabeçalho se a aba não tiver estrutura mínima de metas.
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


def linha_metas_para_dict(cabecalho: list[str], linha: list[Any], indice_linha: int) -> dict:
    """
    Converte uma linha da aba METAS_FINANCEIRAS para o padrão interno.

    A leitura é feita pelo nome real do cabeçalho, não por posição fixa.
    Isso evita que VALOR_ATUAL seja lido como zero quando a aba tem formato
    antigo, coluna ID ausente ou pequenas variações de cabeçalho.
    """

    linha_completa = linha + [""] * max(len(cabecalho) - len(linha), 0)
    bruto = {
        str(cabecalho[indice] or "").strip(): linha_completa[indice]
        for indice in range(len(cabecalho))
    }

    def valor_por_opcoes(opcoes: list[str]) -> Any:
        coluna = localizar_coluna(cabecalho, opcoes)
        if not coluna:
            return ""
        return bruto.get(coluna, "")

    registro = {
        "ID": valor_por_opcoes(["ID", "META_ID", "ID_META"]) or f"LINHA_{indice_linha}",
        "DATA_CADASTRO": valor_por_opcoes(["DATA_CADASTRO", "DATA CADASTRO", "CADASTRO", "CRIADO_EM"]),
        "NOME_META": valor_por_opcoes(["NOME_META", "NOME META", "META", "DESCRICAO", "DESCRIÇÃO"]),
        "CATEGORIA": valor_por_opcoes(["CATEGORIA", "TIPO_META", "TIPO META"]),
        "VALOR_ALVO": valor_por_opcoes(["VALOR_ALVO", "VALOR ALVO", "ALVO", "META_VALOR"]),
        "VALOR_ATUAL": valor_por_opcoes(["VALOR_ATUAL", "VALOR ATUAL", "ATUAL", "SALDO_ATUAL", "SALDO ATUAL"]),
        "DATA_ALVO": valor_por_opcoes(["DATA_ALVO", "DATA ALVO", "PRAZO", "DATA_FINAL", "DATA FINAL"]),
        "PRIORIDADE": valor_por_opcoes(["PRIORIDADE"]),
        "STATUS": valor_por_opcoes(["STATUS", "SITUACAO", "SITUAÇÃO"]),
        "OBSERVACAO": valor_por_opcoes(["OBSERVACAO", "OBSERVAÇÃO", "OBS", "COMENTARIO", "COMENTÁRIO"]),
    }

    return registro


def ler_registros_metas(aba) -> list[dict]:
    """
    Lê METAS_FINANCEIRAS de forma tolerante, preservando VALOR_ATUAL.

    Não usa get_all_records() porque em planilhas existentes ele pode ficar
    sensível a cabeçalhos alterados em versões anteriores.
    """

    valores = aba.get_all_values()

    if not valores or len(valores) <= 1:
        return []

    cabecalho = valores[0]
    registros = []

    for indice_linha, linha in enumerate(valores[1:], start=2):
        if not any(str(celula or "").strip() for celula in linha):
            continue

        registro = linha_metas_para_dict(cabecalho, linha, indice_linha)

        if not str(registro.get("NOME_META") or "").strip():
            continue

        registros.append(registro)

    return registros


def meta_usa_patrimonio_atual(meta: dict) -> bool:
    """
    Identifica metas cujo VALOR_ATUAL deve refletir o patrimônio atual.

    Por decisão da Etapa 4, tanto Reserva de Emergência quanto Aumentar
    Patrimônio usam o mesmo patrimônio atual exibido pelo módulo Patrimônio.
    """

    texto = " ".join(
        [
            normalizar_texto(meta.get("NOME_META")),
            normalizar_texto(meta.get("CATEGORIA")),
            normalizar_texto(meta.get("OBSERVACAO")),
        ]
    )

    if "RESERVA" in texto or "EMERGENCIA" in texto:
        return True

    if "AUMENTAR PATRIMONIO" in texto:
        return True

    if "PATRIMONIO LIQUIDO" in texto:
        return True

    return False


def obter_valor_atual_positivo_das_metas(registros: list[dict]) -> float:
    """
    Fallback seguro: se o módulo Patrimônio não retornar valor, aproveita
    um VALOR_ATUAL positivo já gravado em uma meta patrimonial.
    """

    for linha in registros:
        if not meta_usa_patrimonio_atual(linha):
            continue

        valor = converter_valor(linha.get("VALOR_ATUAL"))

        if valor > 0:
            return valor

    return 0.0

def listar_metas_financeiras(link_planilha: str) -> dict:
    planilha = obter_planilha_por_link(link_planilha)
    aba = obter_aba_metas(planilha)

    registros = ler_registros_metas(aba)

    metas = []

    # Busca o patrimônio atual do módulo Patrimônio. Este valor só será usado
    # se for positivo. Se vier zero, preservamos o VALOR_ATUAL existente na
    # própria aba METAS_FINANCEIRAS.
    patrimonio_atual = 0.0

    try:
        dados_patrimonio = obter_patrimonio_oficial()
        patrimonio_atual = converter_valor(dados_patrimonio.get("patrimonio_total"))
    except Exception:
        patrimonio_atual = 0.0

    # Fallback: se o módulo Patrimônio não conseguir responder no carregamento
    # da tela, usa um VALOR_ATUAL positivo já existente em meta patrimonial.
    if patrimonio_atual <= 0:
        patrimonio_atual = obter_valor_atual_positivo_das_metas(registros)

    for linha in registros:
        if not linha.get("NOME_META"):
            continue

        linha_meta = dict(linha)

        # Regra simples e segura:
        # - Reserva de Emergência usa o patrimônio atual.
        # - Aumentar patrimônio líquido usa o patrimônio atual.
        # - Nunca substitui valor positivo por zero.
        # - Não grava nada na planilha; altera apenas em memória para a tela.
        if patrimonio_atual > 0 and meta_usa_patrimonio_atual(linha_meta):
            linha_meta["VALOR_ATUAL"] = patrimonio_atual

        metas.append(calcular_dados_meta(linha_meta))

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


def obter_mes_ano_atual_siglas() -> tuple[str, str]:
    """
    Retorna mês/ano atuais no padrão usado no sistema.
    """

    meses = [
        "JAN",
        "FEV",
        "MAR",
        "ABR",
        "MAI",
        "JUN",
        "JUL",
        "AGO",
        "SET",
        "OUT",
        "NOV",
        "DEZ",
    ]

    hoje = date.today()
    return meses[hoje.month - 1], str(hoje.year)


def filtrar_registros_por_mes_ano_atual(registros: list[dict]) -> list[dict]:
    """
    Se a aba possuir colunas MES/ANO, mantém somente o mês/ano atual.

    Se não houver essas colunas, retorna os registros originais para não
    quebrar planilhas antigas.
    """

    if not registros:
        return registros

    cabecalhos = list(registros[0].keys())

    coluna_mes = localizar_coluna(
        cabecalhos,
        ["MES", "MÊS", "COMPETENCIA", "COMPETÊNCIA"],
    )
    coluna_ano = localizar_coluna(
        cabecalhos,
        ["ANO", "YEAR"],
    )

    if not coluna_mes or not coluna_ano:
        return registros

    mes_atual, ano_atual = obter_mes_ano_atual_siglas()

    filtrados = []

    for linha in registros:
        mes_linha = normalizar_texto(linha.get(coluna_mes))
        ano_linha = str(linha.get(coluna_ano) or "").strip()

        if mes_linha == normalizar_texto(mes_atual) and ano_linha == ano_atual:
            filtrados.append(linha)

    return filtrados or registros


def aba_parece_movimentacao(titulo: str) -> bool:
    """
    Identifica a aba oficial de movimentações financeiras.

    A sugestão de metas deve usar somente a BASE_LANCAMENTOS, pois os
    extratos importados podem conter os mesmos valores antes/depois da
    classificação e isso infla receitas/despesas.

    Portanto, não usamos abas de EXTRATOS, ORÇAMENTO, RECEITAS ou DESPESAS
    avulsas na sugestão automática.
    """

    titulo_norm = normalizar_texto(titulo)

    abas_validas = {
        "BASE_LANCAMENTOS",
        "BASE LANCAMENTOS",
        "BASE DE LANCAMENTOS",
        "BASE DE LANÇAMENTOS",
    }

    return titulo_norm in abas_validas


def aba_parece_patrimonio(titulo: str) -> bool:
    """
    Identifica apenas abas patrimoniais oficiais.

    A sugestão de metas não deve varrer abas genéricas de investimento,
    carteira ou histórico. Isso evita somar meses anteriores ou saldos
    duplicados e gerar metas com valor muito acima do real.
    """

    titulo_norm = normalizar_texto(titulo)

    abas_validas = {
        "PATRIMONIO",
        "PATRIMÔNIO",
        "PATRIMONIO_FINANCEIRO",
        "PATRIMÔNIO_FINANCEIRO",
        "PATRIMONIO FINANCEIRO",
        "PATRIMÔNIO FINANCEIRO",
    }

    return titulo_norm in abas_validas


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
        registros = filtrar_registros_por_mes_ano_atual(registros)

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
        registros = filtrar_registros_por_mes_ano_atual(registros)

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




def indice_mes_por_sigla_ou_nome(valor: Any) -> int | None:
    """
    Converte mês em número, aceitando JAN/FEV, nome completo ou 1 a 12.
    """

    texto = normalizar_texto(valor)

    if not texto:
        return None

    mapa = {
        "JAN": 1, "JANEIRO": 1, "1": 1, "01": 1,
        "FEV": 2, "FEVEREIRO": 2, "2": 2, "02": 2,
        "MAR": 3, "MARCO": 3, "MARÇO": 3, "3": 3, "03": 3,
        "ABR": 4, "ABRIL": 4, "4": 4, "04": 4,
        "MAI": 5, "MAIO": 5, "5": 5, "05": 5,
        "JUN": 6, "JUNHO": 6, "6": 6, "06": 6,
        "JUL": 7, "JULHO": 7, "7": 7, "07": 7,
        "AGO": 8, "AGOSTO": 8, "8": 8, "08": 8,
        "SET": 9, "SETEMBRO": 9, "9": 9, "09": 9,
        "OUT": 10, "OUTUBRO": 10, "10": 10,
        "NOV": 11, "NOVEMBRO": 11, "11": 11,
        "DEZ": 12, "DEZEMBRO": 12, "12": 12,
    }

    return mapa.get(texto)


def classificar_linha_orcamento_oficial(
    linha: dict,
    coluna_tipo: str | None,
    coluna_categoria: str | None,
) -> str:
    """
    Classifica uma linha de orçamento.

    Por segurança, só considera RECEITA quando houver indicação clara.
    Linhas de INVESTIMENTO/TRANSFERÊNCIA não entram como despesa mensal.
    Quando não houver tipo claro, considera DESPESA, pois no orçamento a maior
    parte das linhas sem tipo explícito representa gasto previsto.
    """

    textos = []

    if coluna_tipo:
        textos.append(normalizar_texto(linha.get(coluna_tipo)))

    if coluna_categoria:
        textos.append(normalizar_texto(linha.get(coluna_categoria)))

    texto = " ".join(textos)

    if "RECEITA" in texto or "ENTRADA" in texto or "SALARIO" in texto or "SALÁRIO" in texto:
        return "RECEITA"

    if "INVESTIMENTO" in texto or "APORTE" in texto or "RESERVA" in texto:
        return "INVESTIMENTO"

    if "TRANSFERENCIA" in texto or "TRANSFERÊNCIA" in texto or "ENTRE CONTAS" in texto:
        return "TRANSFERÊNCIA"

    if "DESPESA" in texto or "SAIDA" in texto or "SAÍDA" in texto or "GASTO" in texto:
        return "DESPESA"

    return "DESPESA"


def obter_totais_orcamento_oficial() -> dict:
    """
    Obtém receita/despesa previstas do módulo oficial de orçamento.

    Regra:
    1. Usa mês/ano corrente se houver valor.
    2. Se não houver, usa o último mês/ano com orçamento cadastrado.
    3. Não estima despesa/renda a partir do patrimônio.
    """

    try:
        from core.financeiro.orcamento_google import ler_orcamento_mensal
    except Exception as erro:
        return {
            "ok": False,
            "criterio": "erro_importacao_orcamento",
            "ano_usado": "",
            "mes_usado": "",
            "total_despesas": 0.0,
            "total_receitas": 0.0,
            "saldo_previsto": 0.0,
            "total_despesas_fmt": formatar_moeda(0),
            "total_receitas_fmt": formatar_moeda(0),
            "saldo_previsto_fmt": formatar_moeda(0),
            "linhas_despesa": 0,
            "linhas_receita": 0,
            "mensagem": f"Não foi possível importar o módulo oficial de orçamento: {erro}",
            "detalhes": [],
        }

    try:
        registros = ler_orcamento_mensal()
    except Exception as erro:
        return {
            "ok": False,
            "criterio": "erro_leitura_orcamento",
            "ano_usado": "",
            "mes_usado": "",
            "total_despesas": 0.0,
            "total_receitas": 0.0,
            "saldo_previsto": 0.0,
            "total_despesas_fmt": formatar_moeda(0),
            "total_receitas_fmt": formatar_moeda(0),
            "saldo_previsto_fmt": formatar_moeda(0),
            "linhas_despesa": 0,
            "linhas_receita": 0,
            "mensagem": f"Não foi possível ler o orçamento mensal: {erro}",
            "detalhes": [],
        }

    hoje = date.today()
    chave_atual = (hoje.year, hoje.month)
    grupos: dict[tuple[int, int], dict] = {}

    for linha in registros or []:
        cabecalhos = list(linha.keys())

        coluna_mes = localizar_coluna(cabecalhos, ["MES", "MÊS", "COMPETENCIA", "COMPETÊNCIA"])
        coluna_ano = localizar_coluna(cabecalhos, ["ANO", "YEAR"])
        coluna_tipo = localizar_coluna(cabecalhos, ["TIPO", "NATUREZA", "RECEITA_DESPESA", "ENTRADA_SAIDA"])
        coluna_categoria = localizar_coluna(cabecalhos, ["CATEGORIA", "GRUPO", "CLASSIFICACAO", "CLASSIFICAÇÃO"])
        coluna_valor = localizar_coluna(
            cabecalhos,
            [
                "VALOR_PREVISTO_NUM",
                "VALOR_PREVISTO",
                "VALOR PREVISTO",
                "PREVISTO",
                "VALOR_ORCADO",
                "VALOR ORÇADO",
                "VALOR ORCADO",
                "VALOR",
            ],
        )

        if not coluna_valor:
            continue

        valor = abs(converter_valor(linha.get(coluna_valor)))

        if valor <= 0:
            continue

        ano_int = hoje.year
        mes_int = hoje.month

        if coluna_ano:
            try:
                ano_int = int(float(str(linha.get(coluna_ano) or "").strip()))
            except Exception:
                ano_int = hoje.year

        if coluna_mes:
            mes_extraido = indice_mes_por_sigla_ou_nome(linha.get(coluna_mes))
            if mes_extraido:
                mes_int = mes_extraido

        classificacao = classificar_linha_orcamento_oficial(
            linha=linha,
            coluna_tipo=coluna_tipo,
            coluna_categoria=coluna_categoria,
        )

        chave = (ano_int, mes_int)
        grupos.setdefault(
            chave,
            {
                "ano": ano_int,
                "mes": mes_int,
                "despesas": 0.0,
                "receitas": 0.0,
                "linhas_despesa": 0,
                "linhas_receita": 0,
            },
        )

        if classificacao == "DESPESA":
            grupos[chave]["despesas"] += valor
            grupos[chave]["linhas_despesa"] += 1
        elif classificacao == "RECEITA":
            grupos[chave]["receitas"] += valor
            grupos[chave]["linhas_receita"] += 1

    grupos_validos = {
        chave: dados
        for chave, dados in grupos.items()
        if float(dados.get("despesas") or 0) > 0 or float(dados.get("receitas") or 0) > 0
    }

    if not grupos_validos:
        return {
            "ok": False,
            "criterio": "sem_orcamento_valido",
            "ano_usado": "",
            "mes_usado": "",
            "total_despesas": 0.0,
            "total_receitas": 0.0,
            "saldo_previsto": 0.0,
            "total_despesas_fmt": formatar_moeda(0),
            "total_receitas_fmt": formatar_moeda(0),
            "saldo_previsto_fmt": formatar_moeda(0),
            "linhas_despesa": 0,
            "linhas_receita": 0,
            "mensagem": "Nenhum orçamento válido foi localizado.",
            "detalhes": [],
        }

    if chave_atual in grupos_validos:
        chave_escolhida = chave_atual
        criterio = "orcamento_mes_corrente"
    else:
        chave_escolhida = max(grupos_validos.keys())
        criterio = "orcamento_ultimo_mes_com_valor"

    dados = grupos_validos[chave_escolhida]
    total_despesas = float(dados.get("despesas") or 0)
    total_receitas = float(dados.get("receitas") or 0)
    saldo_previsto = total_receitas - total_despesas

    return {
        "ok": True,
        "criterio": criterio,
        "ano_usado": str(dados.get("ano")),
        "mes_usado": str(dados.get("mes")).zfill(2),
        "total_despesas": total_despesas,
        "total_receitas": total_receitas,
        "saldo_previsto": saldo_previsto,
        "total_despesas_fmt": formatar_moeda(total_despesas),
        "total_receitas_fmt": formatar_moeda(total_receitas),
        "saldo_previsto_fmt": formatar_moeda(saldo_previsto),
        "linhas_despesa": int(dados.get("linhas_despesa") or 0),
        "linhas_receita": int(dados.get("linhas_receita") or 0),
        "mensagem": (
            "Totais obtidos do orçamento do mês corrente."
            if criterio == "orcamento_mes_corrente"
            else "Totais obtidos do último mês com orçamento cadastrado."
        ),
        "detalhes": [
            {
                "ano": str(valor.get("ano")),
                "mes": str(valor.get("mes")).zfill(2),
                "despesas_fmt": formatar_moeda(valor.get("despesas") or 0),
                "receitas_fmt": formatar_moeda(valor.get("receitas") or 0),
                "linhas_despesa": valor.get("linhas_despesa") or 0,
                "linhas_receita": valor.get("linhas_receita") or 0,
            }
            for _, valor in sorted(grupos_validos.items())
        ],
    }




def meta_eh_reserva_emergencia(meta: dict) -> bool:
    """
    Identifica metas de Reserva de Emergência.

    Essas metas não devem usar o patrimônio total como valor atual. O valor
    atual deve vir apenas da parte líquida/reserva informada no módulo
    Patrimônio, para evitar que imóvel, veículo, previdência ou patrimônio
    total inflem a meta.
    """

    texto = " ".join(
        [
            normalizar_texto(meta.get("NOME_META")),
            normalizar_texto(meta.get("CATEGORIA")),
            normalizar_texto(meta.get("OBSERVACAO")),
        ]
    )

    return "RESERVA" in texto or "EMERGENCIA" in texto


def ativo_parece_reserva_liquida(ativo: dict) -> bool:
    """
    Retorna True apenas para ativos que parecem compor reserva/liquidez.

    A classificação é feita com base nos campos do próprio ativo vindo do
    módulo Patrimônio. Não usa o patrimônio total e não soma todos os ativos.
    """

    texto = " ".join(
        normalizar_texto(valor)
        for valor in ativo.values()
        if valor is not None
    )

    if not texto:
        return False

    bloqueios = [
        "DIVIDA",
        "PASSIVO",
        "FINANCIAMENTO",
        "EMPRESTIMO",
        "EMPRÉSTIMO",
        "IMOVEL",
        "IMÓVEL",
        "VEICULO",
        "VEÍCULO",
        "APARTAMENTO",
        "CASA",
        "APOSENTADORIA",
        "PREVIDENCIA",
        "PREVIDÊNCIA",
    ]

    if any(palavra in texto for palavra in bloqueios):
        return False

    palavras_reserva = [
        "RESERVA",
        "EMERGENCIA",
        "EMERGÊNCIA",
        "LIQUIDEZ",
        "POUPANCA",
        "POUPANÇA",
        "TESOURO SELIC",
        "TESOURO RESERVA",
        "CDB LIQUIDEZ",
        "CAIXINHA",
        "CAIXA RESERVA",
        "NU RESERVA",
    ]

    return any(palavra in texto for palavra in palavras_reserva)


def obter_valor_fim_ativo(ativo: dict) -> float:
    """
    Obtém o valor final do ativo no mês, aceitando variações de chave.
    """

    chaves = [
        "fim",
        "valor_fim",
        "VALOR_FIM",
        "valor_final",
        "VALOR_FINAL",
        "saldo_final",
        "SALDO_FINAL",
        "valor_atual",
        "VALOR_ATUAL",
        "saldo",
        "SALDO",
    ]

    for chave in chaves:
        if chave in ativo:
            valor = converter_valor(ativo.get(chave))
            if valor != 0:
                return valor

    return 0.0


def calcular_reserva_liquida_resumo_patrimonio(resumo: dict) -> dict:
    """
    Calcula a reserva líquida a partir dos ativos do resumo de patrimônio.

    Regra: soma somente VALOR_FIM/fim dos ativos que tenham indicação de
    reserva, emergência, liquidez, poupança, Tesouro Selic/Reserva, CDB
    liquidez ou caixinha.
    """

    ativos = resumo.get("ativos", []) or []
    total_reserva = 0.0
    ativos_reserva = []

    for ativo in ativos:
        if not isinstance(ativo, dict):
            continue

        if not ativo_parece_reserva_liquida(ativo):
            continue

        valor = obter_valor_fim_ativo(ativo)

        if valor <= 0:
            continue

        total_reserva += valor
        ativos_reserva.append(
            {
                "nome": str(
                    ativo.get("nome")
                    or ativo.get("conta")
                    or ativo.get("descricao")
                    or ativo.get("DESCRICAO")
                    or ativo.get("CATEGORIA")
                    or "Ativo de reserva"
                ),
                "valor": valor,
                "valor_fmt": formatar_moeda(valor),
            }
        )

    return {
        "reserva_total": total_reserva,
        "reserva_total_fmt": formatar_moeda(total_reserva),
        "linhas_reserva": len(ativos_reserva),
        "ativos_reserva": ativos_reserva,
    }

def obter_patrimonio_oficial() -> dict:
    """
    Obtém patrimônio pelo módulo oficial de patrimônio.

    Regra:
    1. Usa mês/ano corrente se houver valor.
    2. Se não houver, usa o último mês/ano com patrimônio cadastrado.
    3. Não varre a planilha diretamente.
    4. Calcula, separadamente, a reserva líquida para metas de Reserva.
    """

    try:
        from core.financeiro.patrimonio_google import montar_resumo_patrimonio
    except Exception as erro:
        return {
            "ok": False,
            "criterio": "erro_importacao_patrimonio",
            "ano_usado": "",
            "mes_usado": "",
            "patrimonio_total": 0.0,
            "patrimonio_total_fmt": formatar_moeda(0),
            "reserva_total": 0.0,
            "reserva_total_fmt": formatar_moeda(0),
            "linhas_reserva": 0,
            "linhas_utilizadas": 0,
            "mensagem": f"Não foi possível importar o módulo oficial de patrimônio: {erro}",
            "detalhes_abas": [],
        }

    meses = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
    hoje = date.today()
    tentativas: list[tuple[int, int, str]] = []

    for ano in range(hoje.year, hoje.year - 3, -1):
        mes_limite = hoje.month if ano == hoje.year else 12
        for mes_num in range(mes_limite, 0, -1):
            tentativas.append((ano, mes_num, meses[mes_num - 1]))

    detalhes = []

    for ano, mes_num, mes_sigla in tentativas:
        try:
            resumo = montar_resumo_patrimonio(
                ano=str(ano),
                ano_resumo=str(ano),
                mes_resumo=mes_sigla,
            )
        except Exception as erro:
            detalhes.append({"ano": str(ano), "mes": mes_sigla, "ok": False, "mensagem": str(erro)})
            continue

        ativos = resumo.get("ativos", []) or []
        total = 0.0

        for ativo in ativos:
            total += obter_valor_fim_ativo(ativo)

        if total <= 0:
            for chave in ["total_fim", "total_final", "patrimonio_total", "patrimonio_liquido", "total_patrimonio"]:
                if chave in resumo:
                    total = converter_valor(resumo.get(chave))
                    break

        dados_reserva = calcular_reserva_liquida_resumo_patrimonio(resumo)
        reserva_total = float(dados_reserva.get("reserva_total") or 0)
        linhas_reserva = int(dados_reserva.get("linhas_reserva") or 0)

        tem_dados = bool(resumo.get("tem_dados_mes_resumo")) or total > 0 or reserva_total > 0
        detalhes.append(
            {
                "ano": str(ano),
                "mes": mes_sigla,
                "ok": tem_dados,
                "total_fmt": formatar_moeda(total),
                "reserva_fmt": formatar_moeda(reserva_total),
                "qtd_ativos": len(ativos),
                "qtd_ativos_reserva": linhas_reserva,
            }
        )

        if tem_dados and (total > 0 or reserva_total > 0):
            criterio = "patrimonio_mes_corrente" if ano == hoje.year and mes_num == hoje.month else "patrimonio_ultimo_mes_com_valor"
            return {
                "ok": True,
                "criterio": criterio,
                "ano_usado": str(ano),
                "mes_usado": mes_sigla,
                "patrimonio_total": total,
                "patrimonio_total_fmt": formatar_moeda(total),
                "reserva_total": reserva_total,
                "reserva_total_fmt": formatar_moeda(reserva_total),
                "linhas_reserva": linhas_reserva,
                "ativos_reserva": dados_reserva.get("ativos_reserva", []),
                "linhas_utilizadas": len(ativos) if ativos else 1,
                "mensagem": (
                    "Patrimônio obtido do mês corrente pelo módulo Patrimônio. "
                    "Reserva calculada separadamente por ativos de liquidez/reserva."
                    if criterio == "patrimonio_mes_corrente"
                    else "Patrimônio obtido do último mês com valor pelo módulo Patrimônio. "
                    "Reserva calculada separadamente por ativos de liquidez/reserva."
                ),
                "detalhes_abas": detalhes,
            }

    return {
        "ok": False,
        "criterio": "sem_patrimonio_oficial",
        "ano_usado": "",
        "mes_usado": "",
        "patrimonio_total": 0.0,
        "patrimonio_total_fmt": formatar_moeda(0),
        "reserva_total": 0.0,
        "reserva_total_fmt": formatar_moeda(0),
        "linhas_reserva": 0,
        "linhas_utilizadas": 0,
        "mensagem": "Nenhum patrimônio com valor foi localizado pelo módulo Patrimônio.",
        "detalhes_abas": detalhes,
    }

def montar_sugestoes_metas(
    dados_fluxo: dict,
    dados_patrimonio: dict,
    dados_orcamento: dict | None = None,
) -> list[dict]:
    """
    Monta metas automáticas financeiras, sem metas operacionais.

    Fontes:
    - Despesa mensal: orçamento previsto do mês corrente ou último mês cadastrado.
    - Renda mensal: receita prevista do orçamento.
    - Patrimônio atual: módulo Patrimônio.
    """

    dados_orcamento = dados_orcamento or {}

    despesa_referencia = float(dados_orcamento.get("total_despesas") or 0)
    receita_referencia = float(dados_orcamento.get("total_receitas") or 0)
    saldo_referencia = float(dados_orcamento.get("saldo_previsto") or 0)

    patrimonio_total = float(dados_patrimonio.get("patrimonio_total") or 0)
    linhas_patrimonio = int(dados_patrimonio.get("linhas_utilizadas") or 0)
    patrimonio_valido = patrimonio_total > 0 and linhas_patrimonio > 0

    sugestoes = []

    if despesa_referencia > 0:
        sugestoes.append(
            {
                "nome_meta": "Reserva de emergência de 3 meses",
                "categoria": "Reserva de Emergência",
                "valor_alvo": round(despesa_referencia * 3, 2),
                # Conforme regra adotada na tela: Reserva e Aumentar Patrimônio
                # usam o mesmo patrimônio atual como valor de referência.
                "valor_atual": round(patrimonio_total, 2) if patrimonio_total > 0 else 0,
                "data_alvo": data_alvo_em_meses(12),
                "prioridade": "Alta",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente com base no total de despesas previstas do orçamento. "
                    f"Fonte: {dados_orcamento.get('mensagem', '')} "
                    f"Despesa mensal de referência: {formatar_moeda(despesa_referencia)}. "
                    "Valor alvo calculado como 3 meses dessa despesa."
                ),
            }
        )

    if saldo_referencia > 0:
        sugestoes.append(
            {
                "nome_meta": "Investimento mensal programado",
                "categoria": "Investimento",
                "valor_alvo": round(saldo_referencia * 6, 2),
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(6),
                "prioridade": "Média",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente com base na diferença entre receita prevista "
                    "e despesas previstas do orçamento. "
                    f"Sobra mensal prevista: {formatar_moeda(saldo_referencia)}."
                ),
            }
        )

    if receita_referencia > 0:
        sugestoes.append(
            {
                "nome_meta": "Economizar 10% da renda mensal",
                "categoria": "Investimento",
                "valor_alvo": round(receita_referencia * 0.10 * 6, 2),
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(6),
                "prioridade": "Média",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente com base na receita prevista do orçamento. "
                    f"Receita mensal de referência: {formatar_moeda(receita_referencia)}. "
                    "Valor alvo calculado como 10% da renda durante 6 meses."
                ),
            }
        )

    if despesa_referencia > 0:
        sugestoes.append(
            {
                "nome_meta": "Reduzir despesas variáveis em 10%",
                "categoria": "Outros",
                "valor_alvo": round(despesa_referencia * 0.10 * 6, 2),
                "valor_atual": 0,
                "data_alvo": data_alvo_em_meses(6),
                "prioridade": "Alta",
                "status": "Em andamento",
                "observacao": (
                    "Meta sugerida automaticamente com base no total de despesas previstas do orçamento. "
                    f"Despesa mensal de referência: {formatar_moeda(despesa_referencia)}. "
                    f"Economia estimada em 6 meses: {formatar_moeda(despesa_referencia * 0.10 * 6)}."
                ),
            }
        )

    if patrimonio_valido:
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
                    "Meta sugerida automaticamente com base no patrimônio oficial do mês corrente "
                    "ou do último mês com valor cadastrado. "
                    f"Fonte: {dados_patrimonio.get('mensagem', '')} "
                    f"Patrimônio líquido usado como referência: {formatar_moeda(patrimonio_total)}."
                ),
            }
        )

    sugestoes_validas = []

    for sugestao in sugestoes:
        if converter_valor(sugestao.get("valor_alvo")) <= 0:
            continue

        sugestoes_validas.append(sugestao)

        if len(sugestoes_validas) >= 5:
            break

    return sugestoes_validas

def sugerir_metas_automaticas(
    link_planilha: str,
    origem_sugestao: str = "ANALISE_GERENCIAL",
) -> dict:
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

    # Mantém o diagnóstico de fluxo para a tela, mas os valores principais das metas
    # vêm das fontes oficiais: Orçamento e Patrimônio.
    dados_fluxo = analisar_receitas_despesas(planilha)
    dados_orcamento = obter_totais_orcamento_oficial()
    dados_patrimonio = obter_patrimonio_oficial()

    sugestoes = montar_sugestoes_metas(
        dados_fluxo=dados_fluxo,
        dados_patrimonio=dados_patrimonio,
        dados_orcamento=dados_orcamento,
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
        "origem_sugestao": origem_sugestao,
        "quantidade_cadastrada": len(metas_cadastradas),
        "quantidade_ignorada": len(metas_ignoradas),
        "metas_cadastradas": metas_cadastradas,
        "metas_ignoradas": metas_ignoradas,
        "dados_fluxo": dados_fluxo,
        "dados_patrimonio": dados_patrimonio,
        "dados_orcamento": dados_orcamento,
        "url": planilha.url,
    }