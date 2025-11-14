"""Pydantic schemas shared by the FastAPI endpoints."""

from typing import List

from pydantic import BaseModel


class LottoDrawResponse(BaseModel):
    draw_no: int
    draw_date: str
    numbers: List[int]
    bonus: int


class LottoSyncResponse(BaseModel):
    previous_max: int
    latest: int
    inserted: int
    draws: List[LottoDrawResponse]
