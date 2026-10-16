import json
from pathlib import Path

import pytest
import yaml

from Emulation.traffic_emulator.emulator import (
    build_traffic_plan,
    export_traffic_plan,
    extract_configs,
    filter_rules,
    generate_test_traffic_config,
    load_config,
    load_config_files,
    run,
)

SAMPLE_DIR = Path(__file__).parent / "samples"
ANY_REPLACEMENT = {"src": "192.0.2.1/32", "dst": "198.51.100.1/32"}


@pytest.fixture(scope="module")
def configs():
    return load_config_files(SAMPLE_DIR)


@pytest.fixture(scope="module")
def rules(configs):
    return configs["ASA1.json"]["acl_rules"]


def test_load_config_files(configs):
    assert "ASA1.json" in configs
    assert len(configs["ASA1.json"]["acl_rules"]) == 3


def test_extract_configs_dst_ips(configs):
    ips, acl_rules = extract_configs(configs, ANY_REPLACEMENT, "dst_address")
    assert "10.1.0.1/32" in ips        # first host of 10.1.0.0/24
    assert "10.1.1.5/32" in ips
    assert "172.16.0.10/32" in ips
    assert "198.51.100.1/32" in ips    # any replaced
    assert len(acl_rules) == 3


def test_extract_configs_src_ips(configs):
    ips, _ = extract_configs(configs, ANY_REPLACEMENT, "src_address")
    assert "192.0.2.1/32" in ips       # src any replaced
    assert "192.168.1.1/32" in ips     # first host of 192.168.1.0/24
    assert "10.2.0.1/32" in ips


def test_filter_rules(rules):
    filtered = filter_rules(rules, ["OUTSIDE-IN"])
    assert len(filtered) == 1
    assert filtered[0]["name"] == "OUTSIDE-IN"
    assert filter_rules(rules, None) == rules
    assert filter_rules(rules, []) == rules


def test_generate_test_traffic_config(rules):
    plan = generate_test_traffic_config(rules, ANY_REPLACEMENT)
    # rule1: 1 src x 2 dst x 2 ports = 4; rule2: 1x1x1 = 1; rule3: 1x1x3 = 3
    assert len(plan) == 8

    web = [p for p in plan if p["dst_ip"] == "10.1.0.1/32"]
    assert len(web) == 2
    assert {p["dst_port"] for p in web} == {"80", "443"}
    assert all(p["src_ip"] == "192.0.2.1/32" for p in web)

    mgmt = [p for p in plan if p["dst_port"] == "22"]
    assert mgmt[0]["src_ip"] == "192.168.1.1/32"

    app = [p for p in plan if p["protocol"] == "udp"]
    assert {p["dst_port"] for p in app} == {"17001", "17002", "17003"}
    assert app[0]["dst_ip"] == "198.51.100.1/32"


def test_build_traffic_plan_with_rule_filter(configs):
    settings = {"any_ip_replacement": ANY_REPLACEMENT,
                "rules": ["MGMT"], "address_field": "dst_address"}
    ips, plan = build_traffic_plan(configs, settings)
    assert len(plan) == 1
    assert plan[0]["dst_ip"] == "172.16.0.10/32"


def test_export_traffic_plan_yaml_and_json(tmp_path, rules):
    plan = generate_test_traffic_config(rules, ANY_REPLACEMENT)

    yaml_path = export_traffic_plan(plan, tmp_path / "plan.yaml")
    with open(yaml_path, encoding="utf-8") as fh:
        assert yaml.safe_load(fh) == plan

    json_path = export_traffic_plan(plan, tmp_path / "plan.json")
    with open(json_path, encoding="utf-8") as fh:
        assert json.load(fh) == plan


def test_run_exports_plan_without_interface_setup(tmp_path, monkeypatch):
    input_dir = tmp_path / "ConfigExport"
    input_dir.mkdir()
    (input_dir / "ASA1.json").write_text(
        (SAMPLE_DIR / "ASA1.json").read_text(encoding="utf-8"), encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "input:\n  directory: ConfigExport\n"
        "emulation:\n  rules: [OUTSIDE-IN]\n"
        "  any_ip_replacement: {src: '192.0.2.1/32', dst: '198.51.100.1/32'}\n"
        "output:\n  file: plan.yaml\n"
        "logging:\n  console: false\n  directory: logs\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    run(load_config(str(config_file)))

    plan_path = tmp_path / "plan.yaml"
    assert plan_path.exists()
    with open(plan_path, encoding="utf-8") as fh:
        plan = yaml.safe_load(fh)
    assert len(plan) == 4  # only OUTSIDE-IN: 2 dst x 2 ports
    assert list((tmp_path / "logs").glob("traffic_emulator_*.log"))
