"""Safe, read-only preview of a Mercado Livre reconciliation workbook.

This module deliberately does not guess financial column mappings, persist the
uploaded workbook, or run any reconciliation. Real examples are required first.
"""
import csv
import io
import zipfile
from html import escape

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_SHEETS = 12
MAX_COLUMNS = 45
MAX_ROWS_SCANNED = 20
MAX_SAMPLES = 5
MAX_CELL_CHARS = 180


class PreviewError(ValueError):
    pass


def _cell(value):
    if value is None:
        return ""
    return str(value).replace("\x00", "")[:MAX_CELL_CHARS]


def _preview_rows(rows):
    sample = []
    for row in rows:
        sample.append([_cell(value) for value in list(row)[:MAX_COLUMNS]])
        if len(sample) >= MAX_ROWS_SCANNED:
            break
    if not sample:
        return {"headers": [], "sample": [], "rows_scanned": 0}
    # Header placement differs between reconciliation report versions. Show
    # raw rows; do not assume the first row is a field header.
    return {"headers": sample[0], "sample": sample[:MAX_SAMPLES],
            "rows_scanned": len(sample)}


def preview_reconciliation_upload(filename, payload):
    """Return only a bounded, escaped-at-render-time preview; no storage."""
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise PreviewError("Arquivo vazio ou maior que 2 MB.")
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        if not zipfile.is_zipfile(io.BytesIO(payload)):
            raise PreviewError("O arquivo XLSX não é um Excel válido.")
        # Prevent very small compressed ZIPs from expanding into huge files.
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            entries = zf.infolist()
            if (len(entries) > 250 or
                    sum(entry.file_size for entry in entries) > 20 * 1024 * 1024):
                raise PreviewError("Planilha muito grande para a pré-visualização.")
            if any(entry.flag_bits & 1 for entry in entries):
                raise PreviewError("Planilha criptografada não é aceita.")
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(payload), read_only=True,
                               data_only=True, keep_links=False)
            try:
                if len(wb.sheetnames) > MAX_SHEETS:
                    raise PreviewError("O arquivo contém abas demais.")
                sheets = []
                for ws in wb.worksheets:
                    data = _preview_rows(ws.iter_rows(min_row=1,
                        max_row=MAX_ROWS_SCANNED, max_col=MAX_COLUMNS,
                        values_only=True))
                    sheets.append({"name": _cell(ws.title), **data})
                return sheets
            finally:
                wb.close()
        except PreviewError:
            raise
        except Exception as exc:
            raise PreviewError("Não foi possível ler o arquivo XLSX.") from exc
    if name.endswith(".csv"):
        try:
            content = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                content = payload.decode("cp1252")
            except UnicodeDecodeError as exc:
                raise PreviewError("Codificação CSV não reconhecida.") from exc
        try:
            dialect = csv.Sniffer().sniff(content[:4096], delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
        data = _preview_rows(csv.reader(io.StringIO(content), dialect))
        return [{"name": "CSV", **data}]
    raise PreviewError("Envie uma planilha .xlsx ou .csv. Arquivos .xls não são aceitos.")


def render_reconciliation_preview(sheets):
    parts = ['<div class="card"><h3>Pré-visualização da conciliação</h3>'
             '<p>Os dados abaixo foram lidos apenas para identificar o formato. '
             'Nenhuma divergência foi calculada e o arquivo não foi salvo.</p>']
    for sheet in sheets:
        parts.append('<h4>Aba: ' + escape(sheet["name"]) + '</h4>')
        if not sheet["sample"]:
            parts.append('<p>Aba vazia.</p>')
            continue
        parts.append('<div style="overflow-x:auto"><table><tbody>')
        for row in sheet["sample"]:
            parts.append('<tr>' + ''.join('<td>' + escape(cell) + '</td>'
                                         for cell in row) + '</tr>')
        parts.append('</tbody></table></div>')
        parts.append('<p>Até ' + str(sheet["rows_scanned"])
                     + ' linhas inspecionadas; primeiras '
                     + str(len(sheet["sample"])) + ' exibidas.</p>')
    return ''.join(parts) + '</div>'


# Candidate labels are advisory only; never used to calculate or book charges.
FREIGHT_COLUMN_HINTS = {
    "pedido": ("numero de venda", "número de venda", "order id", "id da venda", "pedido"),
    "envio": ("numero de envio", "número de envio", "shipment id", "id do envio"),
    "frete": ("custo de envio", "tarifa de envio", "shipping fee", "frete"),
    "valor": ("valor", "amount", "montante"),
    "tipo": ("tipo de operacao", "tipo de operação", "transaction type", "descricao"),
}


def identify_reconciliation_columns(sheets):
    """Return possible header positions for review, not financial mappings."""
    import unicodedata

    def normalize(value):
        value = unicodedata.normalize("NFKD", str(value).casefold())
        return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())

    results = []
    for sheet in sheets:
        candidates = []
        for row_number, row in enumerate(sheet.get("sample", [])[:MAX_SAMPLES], 1):
            for col_number, value in enumerate(row[:MAX_COLUMNS], 1):
                normalized = normalize(value)
                if not normalized:
                    continue
                for kind, hints in FREIGHT_COLUMN_HINTS.items():
                    if any(normalize(hint) in normalized for hint in hints):
                        candidates.append({"row": row_number, "column": col_number,
                                           "kind": kind, "label": _cell(value)})
        results.append({"name": _cell(sheet.get("name", "")), "candidates": candidates[:40]})
    return results


def render_reconciliation_column_hints(sheets):
    findings = identify_reconciliation_columns(sheets)
    parts = ['<div class="card"><h3>Possíveis colunas para auditoria</h3>',
             '<p>Identificação preliminar. Confirme os campos com uma planilha real; '
             'nenhum cálculo ou gravação foi realizado.</p>']
    for sheet in findings:
        parts.append('<h4>Aba: ' + escape(sheet["name"]) + '</h4>')
        if not sheet["candidates"]:
            parts.append('<p>Nenhuma coluna candidata identificada na amostra.</p>')
            continue
        parts.append('<ul>')
        for item in sheet["candidates"]:
            parts.append('<li>Linha ' + str(item["row"]) + ', coluna '
                         + str(item["column"]) + ': ' + escape(item["label"])
                         + ' (' + escape(item["kind"]) + ')</li>')
        parts.append('</ul>')
    return ''.join(parts) + '</div>'
