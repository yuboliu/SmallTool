"""Linux traffic emulation test tool.

Refactored from FWConfigParse/lib/cisco_lib.py. Reads the structured JSON
files produced by FW.cisco_acl_parse, builds a test traffic plan from the
ACL rules, exports it (YAML/JSON), and can optionally configure the
destination IPs on Linux ipvlan interfaces so a traffic generator can
reach them.

Fixes from the original:
- any_ip_replacement was a str in one function and a dict in another;
  it is now consistently a {src, dst} dict passed through parameters.
- Pure plan-building logic is separated from Linux system calls.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "input": {"directory": "ConfigExport", "pattern": "*.json",
              "encoding": "utf-8"},
    "emulation": {
        "rules": [],                      # empty list = emulate all ACL rules
        "address_field": "dst_address",   # field used for interface IPs
        "any_ip_replacement": {"src": "192.0.2.1/32", "dst": "198.51.100.1/32"},
        "base_interface": "eth0",
        "setup_interfaces": False,        # Linux only, needs root
    },
    "output": {"file": "traffic_plan.yaml"},
    "logging": {"console": True, "directory": "logs"},
}


def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else Path(__file__).with_name("config.yaml")
    if not config_path.exists():
        return DEFAULT_CONFIG
    with open(config_path, encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    return {section: {**DEFAULT_CONFIG[section], **loaded.get(section, {})}
            for section in DEFAULT_CONFIG}


def setup_logging(log_dir: Path, enable_console: bool = True) -> logging.Logger:
    """Create a logger writing to a timestamped file and optionally console."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"traffic_emulator_{timestamp}.log"

    logger = logging.getLogger("traffic_emulator")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(console_handler)
    return logger


def load_config_files(config_directory: Path, pattern: str = "*.json",
                      encoding: str = "utf-8",
                      logger: logging.Logger | None = None) -> dict:
    """Load all JSON config files (cisco_acl_parse exports) from a directory."""
    loaded_configs = {}
    for filepath in sorted(config_directory.glob(pattern)):
        try:
            with open(filepath, encoding=encoding) as fh:
                config_data = json.load(fh)
            loaded_configs[filepath.name] = config_data
        except (OSError, json.JSONDecodeError) as exc:
            if logger:
                logger.error("Error loading %s: %s", filepath, exc)
    return loaded_configs


def _first_host(address: str) -> str:
    """Return the first host of a network as a /32 (or /128), else *address*."""
    try:
        network = ipaddress.ip_network(address, strict=False)
    except ValueError:
        return address
    if (isinstance(network, ipaddress.IPv4Network) and network.prefixlen < 32) \
            or (isinstance(network, ipaddress.IPv6Network)
                and network.prefixlen < 128):
        first_host = next(network.hosts(), None)
        if first_host:
            suffix = 32 if isinstance(network, ipaddress.IPv4Network) else 128
            return f"{first_host}/{suffix}"
    return address


def extract_configs(config_dict: dict, any_ip_replacement: dict,
                    address_field: str,
                    logger: logging.Logger | None = None) -> tuple:
    """Extract interface IP addresses and ACL rules from loaded configs.

    Returns (ip_addresses, acl_rules). Networks reduce to their first host,
    ``any`` is replaced via *any_ip_replacement*.
    """
    side = "src" if address_field == "src_address" else "dst"
    replacement = any_ip_replacement.get(side, "")

    ip_addresses = []
    acl_rules = []

    def _extract_address(data):
        for key, value in data.items():
            if key == address_field and isinstance(value, str):
                for addr in value.split("\n"):
                    addr = addr.strip()
                    if not addr:
                        continue
                    if addr.lower() == "any":
                        addr = replacement
                    first_host = _first_host(addr)
                    if first_host != addr or _is_valid_network(addr):
                        ip_addresses.append(first_host)
                    elif logger:
                        logger.error("Invalid IP address format: %s", addr)
            elif isinstance(value, dict):
                _extract_address(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _extract_address(item)

    for config in config_dict.values():
        if isinstance(config, dict):
            _extract_address(config)
            acl_rules.extend(config.get("acl_rules", []))
    return ip_addresses, acl_rules


def _is_valid_network(address: str) -> bool:
    try:
        ipaddress.ip_network(address, strict=False)
        return True
    except ValueError:
        return False


def filter_rules(acl_rules: list, emulation_rules: list | None = None) -> list:
    """Keep only rules named in *emulation_rules* (None/empty keeps all)."""
    if not emulation_rules:
        return acl_rules
    return [rule for rule in acl_rules
            if rule.get("name") in emulation_rules]


def _expand_port_range(port_str: str) -> list:
    """Expand a port range string like ``17001-17003`` into single ports."""
    if "-" in port_str:
        start, end = port_str.split("-", 1)
        if start.strip().isdigit() and end.strip().isdigit():
            return [str(port) for port in range(int(start), int(end) + 1)]
    return [port_str]


def generate_test_traffic_config(acl_rules: list, any_ip_replacement: dict,
                                 logger: logging.Logger | None = None) -> list:
    """Expand ACL rules into a flat test traffic plan.

    Each entry: src_ip, dst_ip, dst_port, protocol. Multi-line addresses and
    port ranges are expanded; ``any`` is replaced; networks reduce to their
    first host.
    """
    test_configs = []
    for rule in acl_rules:
        try:
            src_addresses = rule["src_address"].split("\n") \
                if isinstance(rule["src_address"], str) else [rule["src_address"]]
            dst_addresses = rule["dst_address"].split("\n") \
                if isinstance(rule["dst_address"], str) else [rule["dst_address"]]

            dst_ports = []
            if isinstance(rule["dst_port"], str) and rule["dst_port"]:
                for port_part in rule["dst_port"].split("\n"):
                    port_part = port_part.strip()
                    if port_part:
                        dst_ports.extend(_expand_port_range(port_part))
            else:
                dst_ports = ["0"]

            for src_addr in src_addresses:
                if src_addr == "any":
                    src_addr = any_ip_replacement["src"]
                src_addr = _first_host(src_addr)
                for dst_addr in dst_addresses:
                    if dst_addr == "any":
                        dst_addr = any_ip_replacement["dst"]
                    dst_addr = _first_host(dst_addr)
                    for dst_port in dst_ports:
                        test_configs.append({
                            "src_ip": src_addr,
                            "dst_ip": dst_addr,
                            "dst_port": dst_port,
                            "protocol": rule["protocol"],
                        })
        except KeyError as exc:
            if logger:
                logger.error("Invalid rule format, missing key: %s", exc)
    return test_configs


def build_traffic_plan(config_dict: dict, settings: dict,
                       logger: logging.Logger | None = None) -> tuple:
    """Pure logic: loaded JSON configs -> (interface IPs, traffic plan)."""
    any_ip_replacement = settings.get("any_ip_replacement", {})
    ip_addresses, acl_rules = extract_configs(
        config_dict, any_ip_replacement,
        settings.get("address_field", "dst_address"), logger)
    rules = filter_rules(acl_rules, settings.get("rules") or None)
    plan = generate_test_traffic_config(rules, any_ip_replacement, logger)
    return ip_addresses, plan


def configure_veth_interfaces(ip_addresses: list, base_interface: str,
                              logger: logging.Logger) -> tuple:
    """Configure IPs on Linux ipvlan sub-interfaces (requires root, Linux)."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError(
            "Interface setup requires Linux; run with setup_interfaces: false "
            "on other platforms to only export the traffic plan.")

    unique_ips = list(dict.fromkeys(ip_addresses))
    success_count = 0
    for i, ip_addr in enumerate(unique_ips, start=1):
        veth_name = f"veth{i}"
        try:
            subprocess.run(["ip", "link", "add", "link", base_interface,
                            veth_name, "type", "ipvlan", "mode", "l2"],
                           check=True)
            subprocess.run(["ip", "addr", "add", ip_addr, "dev", veth_name],
                           check=True)
            subprocess.run(["ip", "link", "set", veth_name, "up"], check=True)
            logger.info("Successfully configured %s on %s", ip_addr, veth_name)
            success_count += 1
        except (OSError, subprocess.CalledProcessError) as exc:
            logger.error("Failed configuring %s on %s: %s",
                         ip_addr, veth_name, exc)
    return success_count, len(unique_ips)


def export_traffic_plan(plan: list, output_file: Path) -> Path:
    """Write the traffic plan to YAML or JSON (chosen by file extension)."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as fh:
        if output_file.suffix.lower() == ".json":
            json.dump(plan, fh, ensure_ascii=False, indent=2)
        else:
            yaml.safe_dump(plan, fh, allow_unicode=True, sort_keys=False)
    return output_file


def run(config: dict) -> None:
    input_dir = Path(config["input"]["directory"])
    settings = config["emulation"]
    logger = setup_logging(Path(config["logging"]["directory"]),
                           config["logging"].get("console", True))

    if not input_dir.exists():
        logger.error("Input directory not found: %s", input_dir.resolve())
        return
    configs = load_config_files(
        input_dir, config["input"].get("pattern", "*.json"),
        config["input"].get("encoding", "utf-8"), logger)
    if not configs:
        logger.error("No JSON config files found in %s", input_dir.resolve())
        return
    logger.info("Loaded %d config file(s)", len(configs))

    ip_addresses, plan = build_traffic_plan(configs, settings, logger)
    logger.info("Extracted %d interface IPs, generated %d test traffic entries",
                len(ip_addresses), len(plan))

    output_file = export_traffic_plan(plan, Path(config["output"]["file"]))
    logger.info("Traffic plan written to %s", output_file)

    if settings.get("setup_interfaces"):
        success, total = configure_veth_interfaces(
            ip_addresses, settings.get("base_interface", "eth0"), logger)
        logger.info("Configured %d/%d interfaces", success, total)


def main(argv: list | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="traffic_emulator",
        description="Build a test traffic plan from cisco_acl_parse JSON "
                    "exports and optionally set up Linux ipvlan interfaces.")
    parser.add_argument("-c", "--config", default=None,
                        help="Path to config.yaml "
                             "(default: config.yaml next to this tool).")
    args = parser.parse_args(argv)
    run(load_config(args.config))


if __name__ == "__main__":
    sys.exit(main())
