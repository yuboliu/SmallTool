"""Configuration parsing for CLI arguments and YAML config files."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Config:
    """Application configuration."""

    # IPv4 settings
    ipv4_base: Optional[str] = None
    ipv4_prefix: Optional[int] = None

    # IPv6 settings
    ipv6_base: Optional[str] = None
    ipv6_prefix: Optional[int] = None

    # Common settings
    count: int = 1
    switch_is_odd: bool = True
    output_file: Optional[str] = None
    output_format: str = "csv"

    def validate(self) -> None:
        """Validate the configuration."""
        if not self.ipv4_base and not self.ipv6_base:
            raise ValueError("At least one of ipv4_base or ipv6_base must be specified")

        if self.count < 1:
            raise ValueError("Count must be >= 1")

        if self.ipv4_base and self.ipv4_prefix is None:
            raise ValueError("ipv4_prefix is required when ipv4_base is specified")

        if self.ipv6_base and self.ipv6_prefix is None:
            raise ValueError("ipv6_prefix is required when ipv6_base is specified")

        if self.output_format not in ("csv", "json", "text"):
            raise ValueError(f"Unsupported output format: {self.output_format}")


def load_from_yaml(path: str) -> Config:
    """Load configuration from a YAML file."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(**data)


def parse_args(args: Optional[list] = None) -> Config:
    """Parse command line arguments into a Config object."""
    parser = argparse.ArgumentParser(
        prog="subnet_generator",
        description="Generate subnets with address allocation for switches and firewalls.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate IPv4 /29 subnets only
  python -m Subnet.subnet_generator --ipv4-base 10.8.242.0/24 --ipv4-prefix 29 --count 24

  # Generate both IPv4 and IPv6
  python -m Subnet.subnet_generator \\
    --ipv4-base 10.8.242.0/24 --ipv4-prefix 29 \\
    --ipv6-base FC00:0:8:242::/120 --ipv6-prefix 125 \\
    --count 24

  # Use configuration file
  python -m Subnet.subnet_generator --config config.yaml

  # Firewalls get odd addresses, switches get even
  python -m Subnet.subnet_generator --ipv4-base 10.0.0.0/24 --ipv4-prefix 29 --count 8 --firewall-odd
        """,
    )

    parser.add_argument(
        "--config",
        dest="config_file",
        metavar="PATH",
        help="Load configuration from YAML file "
             "(default: config.yaml next to this tool when no network arguments are given)",
    )
    parser.add_argument("--ipv4-base", dest="ipv4_base", metavar="NETWORK",
                        help="IPv4 base network in CIDR notation (e.g., 10.8.242.0/24)")
    parser.add_argument("--ipv4-prefix", dest="ipv4_prefix", type=int, metavar="N",
                        help="IPv4 target prefix length (e.g., 29)")
    parser.add_argument("--ipv6-base", dest="ipv6_base", metavar="NETWORK",
                        help="IPv6 base network in CIDR notation (e.g., FC00:0:8:242::/120)")
    parser.add_argument("--ipv6-prefix", dest="ipv6_prefix", type=int, metavar="N",
                        help="IPv6 target prefix length (e.g., 125)")
    parser.add_argument("--count", type=int, default=1, metavar="N",
                        help="Number of subnets to generate (default: 1)")
    parser.add_argument("--switch-odd", dest="switch_is_odd", action="store_true",
                        default=True,
                        help="Switches use odd addresses, firewalls use even (default)")
    parser.add_argument("--firewall-odd", dest="switch_is_odd", action="store_false",
                        help="Firewalls use odd addresses, switches use even")
    parser.add_argument("--output", dest="output_file", metavar="PATH",
                        help="Output file path (default: stdout)")
    parser.add_argument("--format", dest="output_format",
                        choices=["csv", "json", "text"], default="csv",
                        help="Output format (default: csv)")

    parsed = parser.parse_args(args)

    if parsed.config_file:
        if not Path(parsed.config_file).exists():
            parser.error(f"Config file not found: {parsed.config_file}")
        config = load_from_yaml(parsed.config_file)
    elif parsed.ipv4_base or parsed.ipv6_base:
        config = Config(
            ipv4_base=parsed.ipv4_base,
            ipv4_prefix=parsed.ipv4_prefix,
            ipv6_base=parsed.ipv6_base,
            ipv6_prefix=parsed.ipv6_prefix,
            count=parsed.count,
            switch_is_odd=parsed.switch_is_odd,
            output_file=parsed.output_file,
            output_format=parsed.output_format,
        )
    else:
        default_config = Path(__file__).with_name("config.yaml")
        if not default_config.exists():
            parser.error("No network arguments given and default config.yaml not found")
        config = load_from_yaml(str(default_config))

    try:
        config.validate()
    except ValueError as e:
        parser.error(str(e))

    return config
