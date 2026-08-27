from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class GreenfieldRegistryPressure:
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GreenfieldRegistryPressure":
        if value:
            raise ValueError(f"greenfield registry has no pressure coordinates: {sorted(value)}")
        return cls()

    def to_dict(self) -> dict[str, int]:
        return {}


__all__ = ["GreenfieldRegistryPressure"]
