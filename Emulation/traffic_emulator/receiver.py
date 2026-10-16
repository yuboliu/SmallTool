"""Traffic receiver (B/S server side).

Listens on TCP/UDP ports and logs every arrival as a JSON Lines record
(time, protocol, peer, local address). Deploy it on the far side of the
device under test — typically on the host whose ipvlan interfaces were
configured by the ``plan`` command — to verify which test traffic passed.
"""

from __future__ import annotations

import json
import logging
import select
import socket
import threading
from datetime import datetime
from pathlib import Path


def derive_ports(plan: list) -> tuple:
    """Derive (tcp_ports, udp_ports) from a traffic plan."""
    tcp_ports, udp_ports = [], []
    for entry in plan:
        port_str = str(entry.get("dst_port", ""))
        if not port_str.isdigit() or int(port_str) == 0:
            continue
        port = int(port_str)
        protocol = str(entry.get("protocol", "")).lower()
        if protocol == "tcp" and port not in tcp_ports:
            tcp_ports.append(port)
        elif protocol == "udp" and port not in udp_ports:
            udp_ports.append(port)
    return sorted(tcp_ports), sorted(udp_ports)


class Receiver:
    """Multi-port TCP/UDP listener logging arrivals to a JSONL file."""

    def __init__(self, host: str, tcp_ports: list, udp_ports: list,
                 log_file: Path, logger: logging.Logger | None = None):
        self.host = host
        self.tcp_ports = tcp_ports
        self.udp_ports = udp_ports
        self.log_file = log_file
        self.logger = logger
        self._sockets: list[socket.socket] = []
        self._stop = threading.Event()

    def _open_sockets(self) -> None:
        for port in self.tcp_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, port))
            sock.listen(5)
            sock.setblocking(False)
            self._sockets.append(sock)
        for port in self.udp_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, port))
            sock.setblocking(False)
            self._sockets.append(sock)

    def _log(self, record: dict, log_fh) -> None:
        record["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        log_fh.flush()
        if self.logger:
            self.logger.info("received %s from %s:%s on %s:%s",
                             record["protocol"], record["src_ip"],
                             record["src_port"], record["dst_ip"],
                             record["dst_port"])

    def serve_forever(self) -> None:
        """Serve until stop() is called or Ctrl+C is pressed."""
        self._open_sockets()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        if self.logger:
            self.logger.info("Listening on %s tcp=%s udp=%s",
                             self.host, self.tcp_ports, self.udp_ports)
        with open(self.log_file, "a", encoding="utf-8") as log_fh:
            try:
                while not self._stop.is_set():
                    readable, _, _ = select.select(self._sockets, [], [], 0.5)
                    for sock in readable:
                        if sock.type == socket.SOCK_STREAM:
                            conn, peer = sock.accept()
                            local = conn.getsockname()
                            self._log({"protocol": "tcp",
                                       "src_ip": peer[0], "src_port": peer[1],
                                       "dst_ip": local[0], "dst_port": local[1]},
                                      log_fh)
                            conn.close()
                        else:
                            _, peer = sock.recvfrom(65535)
                            local = sock.getsockname()
                            self._log({"protocol": "udp",
                                       "src_ip": peer[0], "src_port": peer[1],
                                       "dst_ip": local[0], "dst_port": local[1]},
                                      log_fh)
            except KeyboardInterrupt:
                pass
            finally:
                for sock in self._sockets:
                    sock.close()

    def stop(self) -> None:
        self._stop.set()


def run_receiver(settings: dict, logger: logging.Logger) -> None:
    host = settings.get("host", "0.0.0.0")
    tcp_ports = settings.get("tcp_ports") or []
    udp_ports = settings.get("udp_ports") or []
    if not tcp_ports and not udp_ports and settings.get("plan_file"):
        from .sender import load_plan
        plan_file = Path(settings["plan_file"])
        if plan_file.exists():
            tcp_ports, udp_ports = derive_ports(load_plan(plan_file))
            logger.info("Derived ports from %s: tcp=%s udp=%s",
                        plan_file, tcp_ports, udp_ports)
    if not tcp_ports and not udp_ports:
        logger.error("No ports to listen on: set receiver.tcp_ports/udp_ports "
                     "or receiver.plan_file")
        return
    receiver = Receiver(host, tcp_ports, udp_ports,
                        Path(settings.get("log_file", "logs/received.jsonl")),
                        logger)
    receiver.serve_forever()
