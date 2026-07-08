from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.auth.oauth import CredentialsData
from app.docs_reader.models import DocumentContent
from app.errors import DocumentReadError

DOC_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")


def extract_document_id(document_url: str) -> str:
    value = document_url.strip()
    if DOC_ID_RE.match(value):
        return value

    parsed = urlparse(value)
    if parsed.netloc not in {"docs.google.com", "www.docs.google.com"}:
        raise DocumentReadError("Informe uma URL valida do Google Docs.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3 or parts[0] != "document" or parts[1] != "d":
        raise DocumentReadError("A URL precisa seguir o padrao /document/d/{documentId}.")

    document_id = parts[2]
    if not DOC_ID_RE.match(document_id):
        raise DocumentReadError("O documentId da URL parece invalido.")
    return document_id


class GoogleDocsReader:
    def read(self, document_url: str, credentials_data: CredentialsData) -> DocumentContent:
        document_id = extract_document_id(document_url)
        credentials = Credentials(
            token=credentials_data.token,
            refresh_token=credentials_data.refresh_token,
            token_uri=credentials_data.token_uri,
            client_id=credentials_data.client_id,
            client_secret=credentials_data.client_secret,
            scopes=credentials_data.scopes,
        )

        try:
            service = build("docs", "v1", credentials=credentials, cache_discovery=False)
            document = (
                service.documents()
                .get(documentId=document_id, includeTabsContent=True)
                .execute()
            )
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status in {401, 403}:
                raise DocumentReadError(
                    "Nao foi possivel ler o documento. Confirme se sua conta tem acesso.",
                    status_code=403,
                ) from exc
            if status == 404:
                raise DocumentReadError("Documento nao encontrado.", status_code=404) from exc
            raise DocumentReadError("Erro ao chamar a Google Docs API.") from exc

        return google_doc_to_markdown(document_id, document)


def google_doc_to_markdown(document_id: str, document: dict[str, Any]) -> DocumentContent:
    title = document.get("title") or "Documento sem titulo"
    sections: list[str] = [f"# {title}".strip()]

    tabs = document.get("tabs") or []
    if tabs:
        for tab in tabs:
            sections.extend(_tab_to_markdown(tab))
    else:
        sections.extend(_body_to_markdown(document.get("body", {})))

    markdown = "\n\n".join(section for section in sections if section.strip()).strip()
    if not markdown or markdown == f"# {title}":
        raise DocumentReadError("O documento esta vazio ou nao possui texto analisavel.")

    return DocumentContent(document_id=document_id, title=title, markdown=markdown)


def _tab_to_markdown(tab: dict[str, Any]) -> list[str]:
    tab_properties = tab.get("tabProperties", {})
    title = tab_properties.get("title")
    document_tab = tab.get("documentTab", {})
    content = []
    if title:
        content.append(f"## Aba: {title}")
    content.extend(_body_to_markdown(document_tab.get("body", {})))
    for child in tab.get("childTabs", []) or []:
        content.extend(_tab_to_markdown(child))
    return content


def _body_to_markdown(body: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for element in body.get("content", []) or []:
        lines.extend(_structural_element_to_markdown(element))
    return lines


def _structural_element_to_markdown(element: dict[str, Any]) -> list[str]:
    if "paragraph" in element:
        paragraph = _paragraph_to_markdown(element["paragraph"])
        return [paragraph] if paragraph else []
    if "table" in element:
        return _table_to_markdown(element["table"])
    if "tableOfContents" in element:
        return ["[Sumario omitido]"]
    return []


def _paragraph_to_markdown(paragraph: dict[str, Any]) -> str:
    text = "".join(_paragraph_element_text(element) for element in paragraph.get("elements", []))
    text = re.sub(r"\s+\n", "\n", text).strip()
    if not text:
        return ""

    style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
    prefix = _style_prefix(style)

    bullet = paragraph.get("bullet")
    if bullet:
        nesting = int(bullet.get("nestingLevel", 0))
        return f"{'  ' * nesting}- {text}"

    return f"{prefix}{text}" if prefix else text


def _paragraph_element_text(element: dict[str, Any]) -> str:
    if "textRun" in element:
        return element["textRun"].get("content", "")
    if "inlineObjectElement" in element:
        return "[objeto inline omitido]"
    if "horizontalRule" in element:
        return "\n---\n"
    return ""


def _style_prefix(style: str) -> str:
    return {
        "TITLE": "# ",
        "SUBTITLE": "## ",
        "HEADING_1": "## ",
        "HEADING_2": "### ",
        "HEADING_3": "#### ",
        "HEADING_4": "##### ",
        "HEADING_5": "###### ",
    }.get(style, "")


def _table_to_markdown(table: dict[str, Any]) -> list[str]:
    rows: list[list[str]] = []
    for row in table.get("tableRows", []) or []:
        cells: list[str] = []
        for cell in row.get("tableCells", []) or []:
            cell_parts = []
            for item in cell.get("content", []) or []:
                cell_parts.extend(_structural_element_to_markdown(item))
            cells.append(" ".join(part.strip() for part in cell_parts if part.strip()))
        rows.append(cells)

    if not rows:
        return []

    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    markdown_rows = [
        "| " + " | ".join(_escape_table_cell(cell) for cell in row) + " |"
        for row in normalized
    ]
    separator = "| " + " | ".join("---" for _ in range(width)) + " |"
    return [markdown_rows[0], separator, *markdown_rows[1:]]


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
