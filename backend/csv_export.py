"""
Exportação dos dados coletados em CSV pronto para o Excel em pt-BR:
separado por ';', decimais com vírgula e BOM UTF-8 (acentos corretos).
"""

import csv
import io
from datetime import datetime
from typing import Iterable, List, Optional

from fastapi.responses import Response


def num(value: Optional[float], digits: int = 3) -> str:
    return "" if value is None else f"{value:.{digits}f}".replace(".", ",")


def when(value: Optional[datetime]) -> str:
    return value.isoformat(sep=" ", timespec="seconds") if value else ""


def short_id(value) -> str:
    """Identificador curto e anônimo de uma sessão (8 primeiros caracteres)."""
    return str(value)[:8] if value else ""


def csv_response(header: List[str], rows: Iterable[list], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
