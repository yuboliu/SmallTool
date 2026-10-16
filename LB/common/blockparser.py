"""Generic parser for brace-delimited network device configuration files.

Handles the common ``key value`` / ``block { ... }`` format used by
F5 BIG-IP (bigip.conf) and Horizon ADP (startup-config) style configs.
"""

from __future__ import annotations


class Block:
    """A named configuration block with properties and child blocks."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.props: dict[str, str | bool | list] = {}
        self.children: list[Block] = []

    def find(self, name: str) -> "Block | None":
        for child in self.children:
            if child.name == name:
                return child
        return None

    def __repr__(self) -> str:
        return f"Block({self.name!r}, props={len(self.props)}, children={len(self.children)})"


def parse_blocks(text: str) -> Block:
    """Parse *text* into a tree of Blocks; returns the synthetic root block.

    - ``name {`` opens a child block, ``}`` closes it, ``name { }`` is an
      empty child block on one line.
    - ``key value`` lines become string properties; a bare ``key`` becomes
      a boolean flag (True); repeated keys collect into a list.
    """
    root = Block("")
    stack = [root]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith("{ }"):
            stack[-1].children.append(Block(line[:-3].strip()))
        elif line.endswith("{"):
            block = Block(line[:-1].strip())
            stack[-1].children.append(block)
            stack.append(block)
        elif line.startswith("}"):
            if len(stack) > 1:
                stack.pop()
        else:
            key, _, value = line.partition(" ")
            value = value.strip()
            prop: str | bool = value if value else True
            props = stack[-1].props
            if key in props:
                existing = props[key]
                if isinstance(existing, list):
                    existing.append(prop)
                else:
                    props[key] = [existing, prop]
            else:
                props[key] = prop
    return root
