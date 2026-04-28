"""Case conversion between Python snake_case and CLI --kebab-case."""

from __future__ import annotations


def snake_to_kebab(name: str) -> str:
    return name.replace("_", "-")


def kebab_to_snake(name: str) -> str:
    return name.replace("-", "_")
