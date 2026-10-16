"""Output formatting for subnet generation results."""

from __future__ import annotations

import csv
import io
import json
from typing import List, Optional

from .generator import SubnetEntry


def _has(entries: Optional[List[SubnetEntry]]) -> bool:
    return entries is not None and len(entries) > 0


def _headers(entries_v4, entries_v6) -> list:
    headers = []
    if _has(entries_v4):
        headers.extend(["IPv4_Subnet", "IPv4_Switch", "IPv4_Firewall"])
    if _has(entries_v6):
        headers.extend(["IPv6_Subnet", "IPv6_Switch", "IPv6_Firewall"])
    return headers


def _row(entry: SubnetEntry) -> list:
    return [
        str(entry.subnet),
        str(entry.switch_addr) if entry.switch_addr else "",
        str(entry.firewall_addr) if entry.firewall_addr else "",
    ]


def _rows(entries_v4, entries_v6) -> list:
    count = len(entries_v4) if _has(entries_v4) else len(entries_v6 or [])
    rows = []
    for i in range(count):
        row = []
        if _has(entries_v4):
            row.extend(_row(entries_v4[i]))
        if _has(entries_v6):
            row.extend(_row(entries_v6[i]))
        rows.append(row)
    return rows


def format_csv(entries_v4: Optional[List[SubnetEntry]],
               entries_v6: Optional[List[SubnetEntry]]) -> str:
    """Format results as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_headers(entries_v4, entries_v6))
    writer.writerows(_rows(entries_v4, entries_v6))
    return output.getvalue()


def format_json(entries_v4: Optional[List[SubnetEntry]],
                entries_v6: Optional[List[SubnetEntry]]) -> str:
    """Format results as JSON."""
    result = {}
    for key, entries in (("ipv4", entries_v4), ("ipv6", entries_v6)):
        if _has(entries):
            result[key] = [
                {
                    "subnet": str(e.subnet),
                    "switch": str(e.switch_addr) if e.switch_addr else None,
                    "firewall": str(e.firewall_addr) if e.firewall_addr else None,
                }
                for e in entries
            ]
    return json.dumps(result, indent=2)


def format_text(entries_v4: Optional[List[SubnetEntry]],
                entries_v6: Optional[List[SubnetEntry]]) -> str:
    """Format results as aligned text table."""
    lines = ["  ".join(_headers(entries_v4, entries_v6))]
    lines.append("-" * len(lines[0]))
    lines += ["  ".join(row) for row in _rows(entries_v4, entries_v6)]
    return "\n".join(lines)


def write_output(
    entries_v4: Optional[List[SubnetEntry]],
    entries_v6: Optional[List[SubnetEntry]],
    output_format: str,
    output_file: Optional[str] = None,
) -> None:
    """Write formatted output to file or stdout."""
    if output_format == "csv":
        content = format_csv(entries_v4, entries_v6)
    elif output_format == "json":
        content = format_json(entries_v4, entries_v6)
    else:
        content = format_text(entries_v4, entries_v6)

    if output_file:
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            f.write(content.rstrip("\n") + "\n")
        print(f"Output written to: {output_file}")
    else:
        print(content)
