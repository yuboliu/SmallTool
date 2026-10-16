"""Parse Horizon ADP load balancer configuration (startup-config) to Excel.

Refactored from https://github.com/yuboliu/Horizon-ADP_Conf-To-Excel
on top of the shared block parser in LB.common.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from ..common.blockparser import Block, parse_blocks
from ..common.excel import write_workbook

SHEET_ORDER = [
    "ip_nat_pool",
    "health_check",
    "slb_pool",
    "slb_profile",
    "slb_profile_persist",
    "slb_virtual-address",
]

DEFAULT_CONFIG = {
    "input": {"file": "startup-config", "encoding": "utf-8"},
    "output": {"file": "output.xlsx"},
}

_HEX_UNICODE = re.compile(r"%u[0-9A-Fa-f]{4}")
_HEX_UNICODE_SPLIT = re.compile(r"(%u[0-9A-Fa-f]{4})")


def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else Path(__file__).with_name("config.yaml")
    if not config_path.exists():
        return DEFAULT_CONFIG
    with open(config_path, encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    return {section: {**DEFAULT_CONFIG[section], **loaded.get(section, {})}
            for section in DEFAULT_CONFIG}


def decode_unicode(text: str) -> str:
    """Decode Horizon ADP ``%uXXXX`` escaped fragments inside *text*."""
    parts = [part for part in _HEX_UNICODE_SPLIT.split(text) if part]
    decoded = []
    for part in parts:
        if part.startswith("%u"):
            decoded.append(chr(int(part[2:], 16)))
        else:
            decoded.append(part)
    return "".join(decoded)


def _cell(value):
    if isinstance(value, str) and _HEX_UNICODE.search(value):
        return decode_unicode(value)
    if isinstance(value, list):
        return "\r\n".join(str(item) for item in value)
    return value


def _props_dict(block: Block) -> dict:
    return {key: _cell(value) for key, value in block.props.items()}


def _union_columns(rows: list) -> list:
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def _table(rows: list, first_column: str = "Name") -> tuple:
    columns = [first_column] + [c for c in _union_columns(rows) if c != first_column]
    return columns, rows


def _header_pairs(tokens: list) -> dict:
    """Parse ``key value key value ...`` header tokens into a dict."""
    return {tokens[i]: tokens[i + 1] for i in range(0, len(tokens) - 1, 2)}


def build_sheets(text: str) -> dict:
    """Parse startup-config text; return {sheet_name: (columns, rows)}."""
    root = parse_blocks(text)
    sheets: dict[str, tuple] = {name: (["Name"], []) for name in SHEET_ORDER}

    nat_rows, health_rows, pool_rows = [], [], []
    profile_rows, persist_rows, va_rows = [], [], []

    for block in root.children:
        name = block.name
        tokens = name.split()
        if name.startswith("ip nat pool "):
            row = {"Name": tokens[3] if len(tokens) > 3 else ""}
            row.update(_props_dict(block))
            nat_rows.append(row)
        elif name.startswith("health check "):
            row = {"Name": tokens[2] if len(tokens) > 2 else ""}
            row.update(_header_pairs(tokens[3:]))
            row.update(_props_dict(block))
            health_rows.append(row)
        elif name.startswith("slb pool "):
            row = {"Name": tokens[2] if len(tokens) > 2 else ""}
            if len(tokens) > 3:
                row["protocol"] = tokens[3]
            row.update(_props_dict(block))
            pool_rows.append(row)
        elif name.startswith("slb profile persist "):
            row = {"Name": tokens[4] if len(tokens) > 4 else ""}
            row.update(_props_dict(block) or {"Null": True})
            persist_rows.append(row)
        elif name.startswith("slb profile ") and not name.startswith("slb profile node "):
            row = {"Name": tokens[3] if len(tokens) > 3 else ""}
            if len(tokens) > 2:
                row["type"] = tokens[2]
            row.update(_props_dict(block))
            profile_rows.append(row)
        elif name.startswith("slb virtual-address "):
            va_address = tokens[2] if len(tokens) > 2 else ""
            other = [key if value is True else f"{key} {value}"
                     for key, value in block.props.items()]
            port_blocks = [c for c in block.children if c.name.startswith("port ")]
            if not port_blocks:
                va_rows.append({"Virtual_Address": va_address,
                                "Port": "", "Other": "\n".join(other)})
            for port_block in port_blocks:
                row = {"Virtual_Address": va_address, "Port": port_block.name}
                row.update(_props_dict(port_block))
                row["Other"] = "\n".join(other)
                va_rows.append(row)

    sheets["ip_nat_pool"] = _table(nat_rows)
    sheets["health_check"] = _table(health_rows)
    sheets["slb_pool"] = _table(pool_rows)
    sheets["slb_profile"] = _table(profile_rows)
    sheets["slb_profile_persist"] = _table(persist_rows)
    sheets["slb_virtual-address"] = _table(va_rows, first_column="Virtual_Address")
    return sheets


def run(config: dict) -> Path:
    input_path = Path(config["input"]["file"])
    output_path = Path(config["output"]["file"])
    if not input_path.exists():
        print(f"Input file not found: {input_path.resolve()}")
        sys.exit(1)
    text = input_path.read_text(encoding=config["input"].get("encoding", "utf-8"))
    sheets = build_sheets(text)
    write_workbook(output_path, sheets)
    print(f"Writing file {output_path}")
    return output_path


def main(argv: list | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="adp_conf_to_excel",
        description="Convert Horizon ADP startup-config to an Excel workbook.")
    parser.add_argument("-c", "--config", default=None,
                        help="Path to config.yaml "
                             "(default: config.yaml next to this tool).")
    args = parser.parse_args(argv)
    run(load_config(args.config))


if __name__ == "__main__":
    sys.exit(main())
