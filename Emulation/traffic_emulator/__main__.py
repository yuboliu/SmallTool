"""CLI entry: plan (default) / send / receive subcommands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .emulator import load_config, run as run_plan, setup_logging


def main(argv: list | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="traffic_emulator",
        description="Traffic emulation test tool: build a traffic plan from "
                    "standard rule JSON files, send it (sender side), or "
                    "listen for it (receiver side).")
    parser.add_argument("command", nargs="?", default="plan",
                        choices=["plan", "send", "receive"],
                        help="plan (default): build traffic plan from JSON; "
                             "send: replay plan as the sender; "
                             "receive: listen and log arrivals as the receiver.")
    parser.add_argument("-c", "--config", default=None,
                        help="Path to config.yaml "
                             "(default: config.yaml next to this tool).")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    logger = setup_logging(Path(config["logging"]["directory"]),
                           config["logging"].get("console", True))

    if args.command == "plan":
        run_plan(config)
    elif args.command == "send":
        from .sender import run_sender
        run_sender(config["sender"], logger)
    elif args.command == "receive":
        from .receiver import run_receiver
        run_receiver(config["receiver"], logger)


if __name__ == "__main__":
    sys.exit(main())
