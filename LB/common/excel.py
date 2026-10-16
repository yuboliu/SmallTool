"""Small helper for writing table data to an Excel workbook."""

from __future__ import annotations

from openpyxl import Workbook


def write_workbook(path, sheets: dict) -> None:
    """Write *sheets* to an .xlsx file at *path*.

    *sheets* maps a sheet name to ``(columns, rows)`` where *columns* is a
    list of column headers and *rows* is a list of dicts keyed by column.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, (columns, rows) in sheets.items():
        sheet = workbook.create_sheet(title=str(name)[:31])
        sheet.append(list(columns))
        for row in rows:
            sheet.append([row.get(column, "") for column in columns])
    workbook.save(path)
