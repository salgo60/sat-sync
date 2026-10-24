from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sat_sync.models import Identity


class Rule(ABC):
    """Base class for all reconciliation rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique rule identifier."""
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, identities: list[Identity]) -> list[Any]:
        """Evaluate identities and return findings."""
        raise NotImplementedError