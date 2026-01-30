from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HelixQueryResult(BaseModel):
    query_name: str
    data: Any
