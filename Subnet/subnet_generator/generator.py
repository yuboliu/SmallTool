"""Core subnet generation and address allocation logic."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union


@dataclass
class SubnetEntry:
    """Represents a generated subnet with allocated addresses."""
    subnet: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
    switch_addr: Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]
    firewall_addr: Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]


class SubnetGenerator:
    """Generates subnets from a base network with a specified prefix length."""

    def __init__(self, base_network: str, new_prefix: int, count: int):
        self.network = ipaddress.ip_network(base_network, strict=False)
        self.new_prefix = new_prefix
        self.count = count
        self._validate()

    def _validate(self) -> None:
        """Validate that the base network can accommodate the requested subnets."""
        if self.new_prefix < self.network.prefixlen:
            raise ValueError(
                f"Target prefix ({self.new_prefix}) must be >= "
                f"base prefix ({self.network.prefixlen})"
            )

        max_subnets = 2 ** (self.new_prefix - self.network.prefixlen)
        if self.count > max_subnets:
            raise ValueError(
                f"Cannot generate {self.count} /{self.new_prefix} subnets from "
                f"{self.network}: maximum is {max_subnets}"
            )

    def generate(self) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """Generate the requested number of subnets."""
        all_subnets = list(self.network.subnets(new_prefix=self.new_prefix))
        return all_subnets[:self.count]


class AddressAllocator:
    """Allocates addresses within a subnet for switches and firewalls."""

    def __init__(self, switch_is_odd: bool = True):
        self.switch_is_odd = switch_is_odd

    def allocate(
        self, subnet: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
    ) -> Tuple[
        Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]],
        Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]],
    ]:
        """Allocate switch and firewall addresses from a subnet.

        Uses hosts() which automatically excludes network and broadcast addresses.
        Addresses are selected based on parity (odd/even) of their integer value.
        """
        hosts = list(subnet.hosts())

        odd_hosts = [h for h in hosts if int(h) & 1]
        even_hosts = [h for h in hosts if not (int(h) & 1)]

        if self.switch_is_odd:
            switch_addr = odd_hosts[0] if odd_hosts else None
            firewall_addr = even_hosts[0] if even_hosts else None
        else:
            switch_addr = even_hosts[0] if even_hosts else None
            firewall_addr = odd_hosts[0] if odd_hosts else None

        return switch_addr, firewall_addr


class SubnetManager:
    """High-level manager that combines subnet generation and address allocation."""

    def __init__(
        self,
        base_network: str,
        new_prefix: int,
        count: int,
        switch_is_odd: bool = True,
    ):
        self.generator = SubnetGenerator(base_network, new_prefix, count)
        self.allocator = AddressAllocator(switch_is_odd)

    def run(self) -> List[SubnetEntry]:
        """Generate subnets and allocate addresses."""
        subnets = self.generator.generate()
        entries = []

        for subnet in subnets:
            switch_addr, firewall_addr = self.allocator.allocate(subnet)
            entries.append(
                SubnetEntry(
                    subnet=subnet,
                    switch_addr=switch_addr,
                    firewall_addr=firewall_addr,
                )
            )

        return entries
