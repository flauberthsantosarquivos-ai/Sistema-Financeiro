from __future__ import annotations

import io
import re
from pathlib import Path
from uuid import uuid4

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]

CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH = Path("token_financeiro_drive.json")

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def extrair_id_planilha_google(link_ou_id: str) -> str:
    texto = (link_ou_id or "").strip()

    if not texto:
        raise ValueError("Informe o link ou ID da planilha do Google Sheets.")

    padrao = r"/spreadsheets/d/([a-zA-Z0-9-_]+)"
    match = re.search(padrao, texto)

    if match:
        return match.group(1)

    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", texto):
        return texto

    raise ValueError(
        "Não foi possível identificar o ID da planilha. "
        "Cole o link completo do Google Sheets ou apenas o ID da planilha."
    )


def autenticar_drive():
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "Arquivo credentials.json não encontrado na raiz do projeto. "
            "Coloque o credentials.json dentro da pasta SISTEMA FINANCEIRO."
        )

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=creds)


def exportar_planilha_google_para_xlsx(
    link_ou_id: str,
    pasta_destino: str | Path,
) -> Path:
    spreadsheet_id = extrair_id_planilha_google(link_ou_id)

    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    service = autenticar_drive()

    nome_arquivo = f"google_sheets_{spreadsheet_id}_{uuid4().hex}.xlsx"
    caminho_saida = pasta_destino / nome_arquivo

    request = service.files().export_media(
        fileId=spreadsheet_id,
        mimeType=MIME_XLSX,
    )

    with caminho_saida.open("wb") as arquivo:
        downloader = MediaIoBaseDownload(arquivo, request)

        concluido = False
        while not concluido:
            status, concluido = downloader.next_chunk()

    return caminho_saida