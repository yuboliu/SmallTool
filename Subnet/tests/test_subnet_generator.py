import csv
import io
import json

import pytest

from Subnet.subnet_generator.config import Config, load_from_yaml, parse_args
from Subnet.subnet_generator.generator import (
    AddressAllocator,
    SubnetGenerator,
    SubnetManager,
)
from Subnet.subnet_generator.output import format_csv, format_json, format_text


def test_generate_ipv4_subnets():
    generator = SubnetGenerator("10.8.242.0/24", 29, 4)
    subnets = generator.generate()
    assert len(subnets) == 4
    assert str(subnets[0]) == "10.8.242.0/29"
    assert str(subnets[3]) == "10.8.242.24/29"


def test_generate_ipv6_subnets():
    generator = SubnetGenerator("FC00:0:8:242::/120", 125, 2)
    subnets = generator.generate()
    assert str(subnets[0]) == "fc00:0:8:242::/125"
    assert str(subnets[1]) == "fc00:0:8:242::8/125"


def test_generate_too_many_subnets():
    with pytest.raises(ValueError, match="maximum is 32"):
        SubnetGenerator("10.0.0.0/24", 29, 33)


def test_prefix_smaller_than_base():
    with pytest.raises(ValueError, match="must be >="):
        SubnetGenerator("10.0.0.0/24", 23, 1)


def test_allocator_switch_odd():
    allocator = AddressAllocator(switch_is_odd=True)
    subnet = SubnetGenerator("10.0.0.0/29", 29, 1).generate()[0]
    switch, firewall = allocator.allocate(subnet)
    assert str(switch) == "10.0.0.1"
    assert str(firewall) == "10.0.0.2"


def test_allocator_firewall_odd():
    allocator = AddressAllocator(switch_is_odd=False)
    subnet = SubnetGenerator("10.0.0.0/29", 29, 1).generate()[0]
    switch, firewall = allocator.allocate(subnet)
    assert str(switch) == "10.0.0.2"
    assert str(firewall) == "10.0.0.1"


def test_subnet_manager_run():
    manager = SubnetManager("10.0.0.0/24", 29, 2)
    entries = manager.run()
    assert len(entries) == 2
    assert str(entries[0].subnet) == "10.0.0.0/29"
    assert str(entries[1].switch_addr) == "10.0.0.9"


def test_format_csv():
    entries = SubnetManager("10.0.0.0/24", 29, 2).run()
    content = format_csv(entries, None)
    rows = list(csv.reader(io.StringIO(content)))
    assert rows[0] == ["IPv4_Subnet", "IPv4_Switch", "IPv4_Firewall"]
    assert rows[1] == ["10.0.0.0/29", "10.0.0.1", "10.0.0.2"]
    assert len(rows) == 3


def test_format_json_dual_stack():
    entries_v4 = SubnetManager("10.0.0.0/24", 29, 1).run()
    entries_v6 = SubnetManager("FC00::/120", 125, 1).run()
    data = json.loads(format_json(entries_v4, entries_v6))
    assert data["ipv4"][0]["subnet"] == "10.0.0.0/29"
    assert data["ipv6"][0]["subnet"] == "fc00::/125"


def test_format_text():
    entries = SubnetManager("10.0.0.0/24", 29, 1).run()
    text = format_text(entries, None)
    assert "IPv4_Subnet" in text
    assert "10.0.0.0/29" in text


def test_load_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        'ipv4_base: "10.8.242.0/24"\nipv4_prefix: 29\ncount: 24\n'
        'switch_is_odd: true\noutput_format: "csv"\n',
        encoding="utf-8")
    config = load_from_yaml(str(config_file))
    assert config.ipv4_base == "10.8.242.0/24"
    assert config.ipv4_prefix == 29
    assert config.count == 24
    config.validate()


def test_parse_args_cli():
    config = parse_args(["--ipv4-base", "10.0.0.0/24", "--ipv4-prefix", "29",
                         "--count", "8", "--firewall-odd"])
    assert config.ipv4_base == "10.0.0.0/24"
    assert config.count == 8
    assert config.switch_is_odd is False


def test_parse_args_yaml_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text('ipv6_base: "FC00::/120"\nipv6_prefix: 125\ncount: 2\n',
                           encoding="utf-8")
    config = parse_args(["--config", str(config_file)])
    assert config.ipv6_base == "FC00::/120"
    assert config.count == 2


def test_config_validate_requires_base():
    with pytest.raises(ValueError, match="At least one"):
        Config().validate()


def test_main_with_yaml_config(tmp_path, monkeypatch, capsys):
    from Subnet.subnet_generator.__main__ import main
    config_file = tmp_path / "config.yaml"
    output_file = tmp_path / "subnets.csv"
    config_file.write_text(
        'ipv4_base: "10.0.0.0/24"\nipv4_prefix: 29\ncount: 2\n'
        f'output_file: "{output_file.as_posix()}"\n',
        encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["subnet_generator", "--config",
                                     str(config_file)])
    assert main() == 0
    rows = list(csv.reader(output_file.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 3
    assert rows[1][0] == "10.0.0.0/29"
