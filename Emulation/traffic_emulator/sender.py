"""Traffic sender (B/S client side).

Replays a traffic plan produced by the ``plan`` command against the network
under test: TCP connect attempts and UDP datagrams, optionally bound to the
planned source address. Results are written to a report file so the effect
of the firewall policy (permit/deny) can be verified.
"""

from __future__ import annotations

import json
import logging
import socket
from datetime import datetime
from pathlib import Path

import yaml

UDP_PAYLOAD = b"traffic-emulator"


def load_plan(plan_file: Path) -> list:
    """Load a traffic plan from YAML or JSON (chosen by file extension)."""
    with open(plan_file, encoding="utf-8") as fh:
        if plan_file.suffix.lower() == ".json":
            return json.load(fh)
        return yaml.safe_load(fh) or []


def _strip_mask(address: str) -> str:
    return address.split("/")[0]


def send_entry(entry: dict, timeout: float = 2.0,
               bind_source: bool = False) -> dict:
    """Send one traffic plan entry; returns the entry plus a result field."""
    result = dict(entry)
    protocol = str(entry.get("protocol", "")).lower()
    port_str = str(entry.get("dst_port", ""))

    if not port_str.isdigit() or int(port_str) == 0:
        result["result"] = "skipped"
        return result
    port = int(port_str)
    src_ip = _strip_mask(str(entry.get("src_ip", "")))
    dst_ip = _strip_mask(str(entry.get("dst_ip", "")))

    if protocol == "tcp":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            if bind_source and src_ip:
                sock.bind((src_ip, 0))
            code = sock.connect_ex((dst_ip, port))
            result["result"] = "reachable" if code == 0 else f"failed({code})"
        except OSError as exc:
            result["result"] = f"error({exc})"
        finally:
            sock.close()
    elif protocol == "udp":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            if bind_source and src_ip:
                sock.bind((src_ip, 0))
            sock.sendto(UDP_PAYLOAD, (dst_ip, port))
            result["result"] = "sent"
        except OSError as exc:
            result["result"] = f"error({exc})"
        finally:
            sock.close()
    else:
        result["result"] = "skipped"
    return result


def send_plan(plan: list, timeout: float = 2.0, bind_source: bool = False,
              logger: logging.Logger | None = None) -> list:
    """Send every entry in the plan; returns the report rows."""
    report = []
    for entry in plan:
        result = send_entry(entry, timeout, bind_source)
        result["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report.append(result)
        if logger:
            logger.info("%s %s:%s/%s -> %s",
                        result["result"],
                        result.get("dst_ip"), result.get("dst_port"),
                        result.get("protocol"),
                        result.get("src_ip"))
    return report


def save_report(report: list, report_file: Path) -> Path:
    """Write the send report to YAML or JSON (chosen by file extension)."""
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as fh:
        if report_file.suffix.lower() == ".json":
            json.dump(report, fh, ensure_ascii=False, indent=2)
        else:
            yaml.safe_dump(report, fh, allow_unicode=True, sort_keys=False)
    return report_file


def run_sender(settings: dict, logger: logging.Logger) -> list | None:
    plan_file = Path(settings.get("plan_file", "traffic_plan.yaml"))
    if not plan_file.exists():
        logger.error("Plan file not found: %s", plan_file.resolve())
        return None
    plan = load_plan(plan_file)
    logger.info("Loaded %d plan entries from %s", len(plan), plan_file)
    report = send_plan(plan,
                       settings.get("timeout", 2.0),
                       settings.get("bind_source", False),
                       logger)
    report_file = save_report(report, Path(settings.get("report_file",
                                                        "send_report.yaml")))
    logger.info("Report written to %s", report_file)
    return report
