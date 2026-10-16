"""Parse F5 BIG-IP LTM configuration (bigip.conf) into CSV files and Excel.

Refactored from https://github.com/yuboliu/f5-conf-to-csv:
no pandas / sqlite / xlsxwriter required — stdlib csv + openpyxl only.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml

from ..common.blockparser import Block, parse_blocks
from ..common.excel import write_workbook

MONITOR_FIELDS = [
    ("Adaptive", "adaptive"),
    ("Defaults_From", "defaults-from"),
    ("Destination", "destination"),
    ("Interval", "interval"),
    ("IP_DSCP", "ip-dscp"),
    ("Recv", "recv"),
    ("Recv_Disable", "recv-disable"),
    ("Send", "send"),
    ("Time_Until_Up", "time-until-up"),
    ("Timeout", "timeout"),
    ("Cipher_List", "cipherlist"),
    ("Compatibility", "compatibility"),
]

PERSISTENCE_FIELDS = [
    ("Always_Send", "always-send"),
    ("App_Service", "app-service"),
    ("Cookie_Encryption", "cookie-encryption"),
    ("Cookie_name", "cookie-name"),
    ("Defaults_From", "defaults-from"),
    ("Encrypt_Cookie_Poolname", "encrypt-cookie-poolname"),
    ("Expiration", "expiration"),
    ("Hash_Length", "hash-length"),
    ("Hash_Offset", "hash-offset"),
    ("HTTP_Only", "httponly"),
    ("Mask", "mask"),
    ("Match_Across_Pools", "match-across-pools"),
    ("Match_Across_Services", "match-across-services"),
    ("Match_Across_Virtuals", "match-across-virtuals"),
    ("Method", "method"),
    ("Mirror", "mirror"),
    ("Override_Connection_Limit", "override-connection-limit"),
    ("Secure", "secure"),
    ("Timeout", "timeout"),
]

PROFILE_FIELDS = [
    ("App_Service", "app-service"),
    ("Cache_Aging_Rate", "cache-aging-rate"),
    ("Cache_Client_Cache_Control_Mode", "cache-client-cache-control-mode"),
    ("Cache_Insert_Age_Header", "cache-insert-age-header"),
    ("Cache_Max_Age", "cache-max-age"),
    ("Cache_Max_Entries", "cache-max-entries"),
    ("Cache_Object_Min_Size", "cache-object-min-size"),
    ("Cache_Object_Max_Size", "cache-object-max-size"),
    ("Cache_Size", "cache-size"),
    ("Cache_Uri_Exclude", "cache-uri-exclude"),
    ("Cache_Uri_Include", "cache-uri-include"),
    ("Cache_Uri_Include_Override", "cache-uri-include-override"),
    ("Cache_Uri_Pinned", "cache-uri-pinned"),
    ("Cert", "cert"),
    ("Chain", "chain"),
    ("Cipher_Group", "cipher-group"),
    ("Ciphers", "ciphers"),
    ("Defaults_From", "defaults-from"),
    ("ECN", "ecn"),
    ("Idle_Timeout", "idle-timeout"),
    ("Inherit_CertKeyChain", "inherit-certkeychain"),
    ("Key", "key"),
    ("Metadata_Cache_Max_Size", "metadata-cache-max-size"),
    ("Options", "options"),
    ("Passphrase", "passphrase"),
    ("Port", "port"),
    ("Proxy_Buffer_Low", "proxy-buffer-low"),
    ("Proxy_Buffer_High", "proxy-buffer-high"),
    ("Receive_Window_Size", "receive-window-size"),
    ("Send_Buffer_Size", "send-buffer-size"),
]

VIRTUAL_SERVER_FIELDS = [
    ("Description", "description"),
    ("Destination", "destination"),
    ("IP_Protocol", "ip-protocol"),
    ("Mask", "mask"),
    ("Pool", "pool"),
    ("Source", "source"),
    ("Translate_Address", "translate-address"),
    ("Translate_port", "translate-port"),
]

VIRTUAL_ADDRESS_FIELDS = [
    ("Address", "address"),
    ("Arp", "arp"),
    ("Mask", "mask"),
    ("Icmp_Echo", "icmp-echo"),
    ("Traffic_Group", "traffic-group"),
    ("Spanning", "spanning"),
]

SHEET_ORDER = [
    "f5-nodes",
    "f5-pools",
    "f5-virtualaddresses",
    "f5-virtualservers",
    "f5-monitors",
    "f5-profiles",
    "f5-persistence",
    "f5-rules",
    "f5-overview",
]

DEFAULT_CONFIG = {
    "input": {"directory": ".", "pattern": "*.conf", "encoding": "utf-8"},
    "output": {"directory": "Output", "formats": ["csv", "excel"]},
}


def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else Path(__file__).with_name("config.yaml")
    if not config_path.exists():
        return DEFAULT_CONFIG
    with open(config_path, encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    config = {section: {**DEFAULT_CONFIG[section], **loaded.get(section, {})}
              for section in DEFAULT_CONFIG}
    return config


def _value(prop) -> str:
    if prop is True:
        return "true"
    if isinstance(prop, list):
        return "; ".join(str(item) for item in prop)
    return str(prop)


def _props_row(block: Block, fields: list) -> dict:
    return {column: _value(block.props[key]) if key in block.props else ""
            for column, key in fields}


def _typed_name_row(remainder: str) -> dict:
    """Split ``"<type> <name>"`` stanza remainder into a Name/Type row."""
    tokens = remainder.split()
    return {"Name": tokens[1] if len(tokens) > 1 else "",
            "Type": tokens[0] if tokens else ""}


def _block_summary(block: Block | None) -> str:
    """Render a sub-block (profiles/rules/persist/snat) as ``; ``-joined text."""
    if block is None:
        return ""
    parts = [child.name for child in block.children]
    parts += [key if value is True else f"{key} {_value(value)}"
              for key, value in block.props.items()]
    return "; ".join(parts)


def _extract_rules(text: str) -> list:
    """Extract iRule raw text via brace counting (TCL is not key/value)."""
    rules = []
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()
        if stripped.startswith("ltm rule ") and stripped.endswith("{"):
            name = stripped[len("ltm rule "):-1].strip()
            depth = 1
            body = []
            idx += 1
            while idx < len(lines) and depth > 0:
                depth += lines[idx].count("{") - lines[idx].count("}")
                if depth > 0:
                    body.append(lines[idx])
                idx += 1
            rules.append((name, "\n".join(body).strip()))
        else:
            idx += 1
    return rules


def extract_tables(text: str) -> dict:
    """Parse bigip.conf text; return {sheet_name: (columns, rows)}."""
    root = parse_blocks(text)

    nodes, pools, virtual_addresses, virtual_servers = [], [], [], []
    monitors, profiles, persistence = [], [], []

    for stanza in root.children:
        name = stanza.name
        if name.startswith("ltm node "):
            nodes.append({
                "Name": name[len("ltm node "):],
                "Address": _value(stanza.props.get("address", "")),
            })
        elif name.startswith("ltm pool "):
            pool_name = name[len("ltm pool "):]
            monitor = _value(stanza.props.get("monitor", ""))
            lb_mode = _value(stanza.props.get("load-balancing-mode", ""))
            members_block = stanza.find("members")
            members = members_block.children if members_block else []
            if not members:
                pools.append({"Name": pool_name, "Member_Name": "",
                              "Member_Address": "", "Monitor": monitor,
                              "LB_Mode": lb_mode})
            for member in members:
                pools.append({
                    "Name": pool_name,
                    "Member_Name": member.name,
                    "Member_Address": _value(member.props.get("address", "")),
                    "Monitor": monitor,
                    "LB_Mode": lb_mode,
                })
        elif name.startswith("ltm virtual-address "):
            row = {"Name": name[len("ltm virtual-address "):]}
            row.update(_props_row(stanza, VIRTUAL_ADDRESS_FIELDS))
            virtual_addresses.append(row)
        elif name.startswith("ltm virtual "):
            row = {"Name": name[len("ltm virtual "):]}
            row.update(_props_row(stanza, VIRTUAL_SERVER_FIELDS))
            row["IP_Forward"] = "True" if "ip-forward" in stanza.props else ""
            row["Profiles"] = _block_summary(stanza.find("profiles"))
            row["Rules"] = _block_summary(stanza.find("rules"))
            row["Persist"] = _block_summary(stanza.find("persist"))
            row["Source_Address_Translation"] = _block_summary(
                stanza.find("source-address-translation"))
            virtual_servers.append(row)
        elif name.startswith("ltm monitor "):
            row = _typed_name_row(name[len("ltm monitor "):])
            row.update(_props_row(stanza, MONITOR_FIELDS))
            monitors.append(row)
        elif name.startswith("ltm profile "):
            row = _typed_name_row(name[len("ltm profile "):])
            row.update(_props_row(stanza, PROFILE_FIELDS))
            profiles.append(row)
        elif name.startswith("ltm persistence "):
            row = _typed_name_row(name[len("ltm persistence "):])
            row.update(_props_row(stanza, PERSISTENCE_FIELDS))
            persistence.append(row)

    rules = [{"Name": rule_name, "Rule": rule_text}
             for rule_name, rule_text in _extract_rules(text)]

    overview = []
    for pool in pools:
        matched = [vs for vs in virtual_servers if vs["Pool"] == pool["Name"]]
        for vs in matched or [None]:
            overview.append({
                "VirtualServer": vs["Name"] if vs else "",
                "Destination": vs["Destination"] if vs else "",
                "Pool": pool["Name"],
                "Pool Member": pool["Member_Name"],
                "Member_Address": pool["Member_Address"],
                "LB_Mode": pool["LB_Mode"],
                "Protocol": vs["IP_Protocol"] if vs else "",
                "Profiles": vs["Profiles"] if vs else "",
                "Rules": vs["Rules"] if vs else "",
                "Persist": vs["Persist"] if vs else "",
                "Monitor": pool["Monitor"],
            })

    tables = {
        "f5-nodes": (["Name", "Address"], nodes),
        "f5-pools": (["Name", "Member_Name", "Member_Address", "Monitor", "LB_Mode"], pools),
        "f5-virtualaddresses": (["Name"] + [c for c, _ in VIRTUAL_ADDRESS_FIELDS], virtual_addresses),
        "f5-virtualservers": (["Name", "Description", "Destination", "IP_Forward",
                               "IP_Protocol", "Mask", "Pool", "Profiles", "Rules",
                               "Persist", "Source", "Source_Address_Translation",
                               "Translate_Address", "Translate_port"], virtual_servers),
        "f5-monitors": (["Name", "Type"] + [c for c, _ in MONITOR_FIELDS], monitors),
        "f5-profiles": (["Name", "Type"] + [c for c, _ in PROFILE_FIELDS], profiles),
        "f5-persistence": (["Name", "Type"] + [c for c, _ in PERSISTENCE_FIELDS], persistence),
        "f5-rules": (["Name", "Rule"], rules),
        "f5-overview": (["VirtualServer", "Destination", "Pool", "Pool Member",
                         "Member_Address", "LB_Mode", "Protocol", "Profiles",
                         "Rules", "Persist", "Monitor"], overview),
    }
    return tables


def convert_file(conf_path: Path, output_dir: Path, formats: list) -> Path:
    """Convert one bigip.conf; returns the output directory used."""
    text = conf_path.read_text(encoding="utf-8")
    tables = extract_tables(text)
    target_dir = output_dir / conf_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    if "csv" in formats:
        for sheet in SHEET_ORDER:
            columns, rows = tables[sheet]
            csv_path = target_dir / f"{sheet}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            print(f"Writing file {csv_path}")
    if "excel" in formats:
        excel_path = target_dir / f"{conf_path.stem}.xlsx"
        write_workbook(excel_path, {sheet: tables[sheet] for sheet in SHEET_ORDER})
        print(f"Writing file {excel_path}")
    return target_dir


def run(config: dict) -> None:
    input_dir = Path(config["input"]["directory"])
    pattern = config["input"].get("pattern", "*.conf")
    output_dir = Path(config["output"]["directory"])
    formats = config["output"].get("formats", ["csv", "excel"])

    conf_files = sorted(input_dir.glob(pattern))
    if not conf_files:
        print(f"No files matching '{pattern}' found in {input_dir.resolve()}")
        return
    for conf_file in conf_files:
        print(f"Processing {conf_file}")
        convert_file(conf_file, output_dir, formats)


def main(argv: list | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="f5_conf_to_csv",
        description="Convert F5 BIG-IP LTM bigip.conf files to CSV and Excel.")
    parser.add_argument("-c", "--config", default=None,
                        help="Path to config.yaml "
                             "(default: config.yaml next to this tool).")
    args = parser.parse_args(argv)
    run(load_config(args.config))


if __name__ == "__main__":
    sys.exit(main())
