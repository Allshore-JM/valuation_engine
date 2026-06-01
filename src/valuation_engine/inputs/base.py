"""Standard return type for every input-estimation function."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Estimate(BaseModel):
    """A single estimated input plus an auditable rationale and any warnings.

    Input modules are pure functions returning one of these, so the final report can
    show every number alongside *why* it was chosen and what fed into it.
    """

    value: float
    rationale: str
    inputs_used: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    def __float__(self) -> float:
        return float(self.value)
