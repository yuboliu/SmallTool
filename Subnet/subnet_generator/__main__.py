"""CLI entry point for the subnet generator."""

from __future__ import annotations

import sys

from .config import parse_args
from .generator import SubnetManager
from .output import write_output


def main() -> int:
    """Main entry point."""
    try:
        config = parse_args()
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1

    entries_v4 = None
    entries_v6 = None

    try:
        if config.ipv4_base:
            manager = SubnetManager(
                base_network=config.ipv4_base,
                new_prefix=config.ipv4_prefix,
                count=config.count,
                switch_is_odd=config.switch_is_odd,
            )
            entries_v4 = manager.run()
            print(f"Generated {len(entries_v4)} IPv4 /{config.ipv4_prefix} subnets from {config.ipv4_base}")

        if config.ipv6_base:
            manager = SubnetManager(
                base_network=config.ipv6_base,
                new_prefix=config.ipv6_prefix,
                count=config.count,
                switch_is_odd=config.switch_is_odd,
            )
            entries_v6 = manager.run()
            print(f"Generated {len(entries_v6)} IPv6 /{config.ipv6_prefix} subnets from {config.ipv6_base}")

        write_output(
            entries_v4=entries_v4,
            entries_v6=entries_v6,
            output_format=config.output_format,
            output_file=config.output_file,
        )

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
