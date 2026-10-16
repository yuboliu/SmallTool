"""Extract address sets, service sets and security policies from Huawei
USG firewall configuration text.

Refactored from FWConfigParse/lib/extract_*.py: functions take config
text/lines instead of file paths so they are directly testable.
"""

from __future__ import annotations

import re


def extract_address_sets(content: str) -> list:
    """Extract all ``ip address-set`` blocks from config text.

    Returns a list of dicts: set_name, set_type, addresses (newline-joined).
    """
    address_set_pattern = (
        r"ip address-set\s+(\S+)\s+type\s+(\S+)[\s\S]+?(?=^ip address-set|^$|^#)"
    )
    matches = re.finditer(address_set_pattern, content, re.MULTILINE)

    address_sets = []
    for match in matches:
        set_name = match.group(1)
        set_type = match.group(2)
        set_content = match.group(0)

        addresses = []
        # address <index> <ip> mask <len> (IPv4 and IPv6)
        mask_pattern = r"address\s+(\d+)\s+([\da-fA-F:.]+)\s+mask\s+(\d+)"
        for m in re.finditer(mask_pattern, set_content):
            addresses.append(f"{m.group(2)}/{m.group(3)}")

        # address <index> range <start_ip> <end_ip> (IPv4 and IPv6)
        range_pattern = r"address\s+(\d+)\s+range\s+([\da-fA-F:.]+)\s+([\da-fA-F:.]+)"
        for m in re.finditer(range_pattern, set_content):
            addresses.append(f"{m.group(2)} - {m.group(3)}")

        address_sets.append({
            "set_name": set_name,
            "set_type": set_type,
            "addresses": "\n".join(addresses) if addresses else "",
        })

    return address_sets


def extract_service_sets(lines: list) -> list:
    """Extract all ``ip service-set ... type object`` blocks from config lines.

    Returns a list of dicts: service_set_name, services (newline-joined).
    """
    service_sets = []
    current_service_set = None
    current_services = []
    in_service_set = False

    def save_current():
        service_sets.append({
            "service_set_name": current_service_set,
            "services": "\n".join(current_services) if current_services else "",
        })

    for line in lines:
        stripped_line = line.strip()

        if stripped_line.startswith("ip service-set ") \
                and "type object" in stripped_line:
            if current_service_set:
                save_current()
            current_service_set = stripped_line.split(" ")[2]
            current_services = []
            in_service_set = True
            continue

        if in_service_set and stripped_line == "#":
            # Huawei configs use "#" as a section separator
            save_current()
            in_service_set = False
            current_service_set = None
            current_services = []
            continue

        if in_service_set and stripped_line.startswith("service ") \
                and "protocol" in stripped_line \
                and "destination-port" in stripped_line:
            protocol_match = re.search(r"protocol\s+(\w+)", stripped_line)
            protocol = protocol_match.group(1) if protocol_match else ""
            if " to " in stripped_line:
                port_match = re.search(r"destination-port\s+(\d+)\s+to\s+(\d+)",
                                       stripped_line)
                if port_match:
                    current_services.append(
                        f"{protocol} {port_match.group(1)} to {port_match.group(2)}")
            else:
                port_match = re.search(r"destination-port\s+(\d+)", stripped_line)
                if port_match:
                    current_services.append(f"{protocol} {port_match.group(1)}")

        if in_service_set and current_service_set \
                and stripped_line.startswith("ip ") \
                and not stripped_line.startswith("ip service-set "):
            save_current()
            in_service_set = False
            current_service_set = None
            current_services = []

    if current_service_set:
        save_current()

    unique_service_sets = []
    seen_names = set()
    for service_set in service_sets:
        if service_set["service_set_name"] not in seen_names:
            seen_names.add(service_set["service_set_name"])
            unique_service_sets.append(service_set)

    return unique_service_sets


def extract_security_policies(lines: list) -> list:
    """Extract rules from the ``security-policy`` block in config lines.

    Returns a list of dicts: rule_name, source_zone, destination_zone,
    source_address, destination_address, service, action.
    """
    in_security_policy = False
    security_policy_lines = []

    for line in lines:
        stripped_line = line.strip()

        if stripped_line == "security-policy":
            in_security_policy = True
            continue

        if in_security_policy:
            if stripped_line.endswith("-policy") \
                    and not stripped_line.startswith(" "):
                break
            security_policy_lines.append(line)

    if not security_policy_lines:
        return []

    rules = []
    current_rule = None

    for line in security_policy_lines:
        stripped_line = line.strip()

        if not stripped_line or stripped_line.startswith("default"):
            continue

        if stripped_line.startswith("rule name "):
            if current_rule:
                rules.append(current_rule)
            current_rule = {
                "rule_name": stripped_line.split("rule name ")[1],
                "source_zone": [],
                "destination_zone": [],
                "source_address": [],
                "destination_address": [],
                "service": [],
                "action": "",
            }
        elif current_rule and stripped_line:
            if stripped_line.startswith("source-zone "):
                current_rule["source_zone"].append(
                    stripped_line.split("source-zone ")[1])
            elif stripped_line.startswith("destination-zone "):
                current_rule["destination_zone"].append(
                    stripped_line.split("destination-zone ")[1])
            elif stripped_line.startswith("source-address "):
                address = stripped_line.split("source-address ")[1]
                if address.startswith("address-set "):
                    address = address.split("address-set ")[1]
                current_rule["source_address"].append(address)
            elif stripped_line.startswith("destination-address "):
                address = stripped_line.split("destination-address ")[1]
                if address.startswith("address-set "):
                    address = address.split("address-set ")[1]
                current_rule["destination_address"].append(address)
            elif stripped_line.startswith("service "):
                current_rule["service"].append(stripped_line.split("service ")[1])
            elif stripped_line.startswith("action "):
                current_rule["action"] = stripped_line.split("action ")[1]

    if current_rule:
        rules.append(current_rule)

    for rule in rules:
        for key in ("source_zone", "destination_zone", "source_address",
                    "destination_address", "service"):
            rule[key] = ", ".join(rule[key])

    return rules
