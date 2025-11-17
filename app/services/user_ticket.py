"""Service helpers to store user-submitted Lotto tickets and their outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pymongo import ReturnDocument

from app.core.config import get_settings
from app.core.db import get_mongo_client
from app.services.lotto import (
    evaluate_ticket,
    fetch_draw_info,
    fetch_latest_draw_info,
    get_latest_stored_draw,
    get_stored_draw,
)


class UserTicketError(ValueError):
    """Raised when user ticket processing fails."""


def _latest_known_draw_no() -> Optional[int]:
    latest_stored = get_latest_stored_draw()
    latest_remote: int | None = None
    try:
        latest_remote = fetch_latest_draw_info().draw_no
    except ValueError:
        latest_remote = None

    if latest_stored is not None and latest_remote is not None:
        return max(latest_stored.draw_no, latest_remote)
    if latest_stored is not None:
        return latest_stored.draw_no
    if latest_remote is not None:
        return latest_remote
    return None


def _user_ticket_collection():
    settings = get_settings()
    if not settings.use_mongo_storage:
        raise UserTicketError("MongoDB 백엔드에서만 사용자 티켓 저장이 가능합니다.")

    client = get_mongo_client()
    collection = client[settings.mongo_db_name][
        settings.mongo_user_ticket_collection_name
    ]
    collection.create_index(
        [("user_id", 1), ("draw_no", 1), ("numbers", 1)],
        unique=True,
    )
    collection.create_index("created_at")
    return collection


def save_user_ticket(
    user_id: str,
    draw_no: int,
    numbers: List[int],
) -> Dict[str, object]:
    if not user_id:
        raise UserTicketError("userId가 비어 있습니다.")
    if draw_no <= 0:
        raise UserTicketError("회차 번호는 1 이상이어야 합니다.")

    latest_known = _latest_known_draw_no()
    if latest_known is not None and draw_no > latest_known:
        raise UserTicketError(
            f"{draw_no}회차는 아직 추첨되지 않았어요. 가장 최근 추첨은 {latest_known}회차입니다."
        )

    settings = get_settings()
    draw = None
    if settings.use_mongo_storage:
        draw = get_stored_draw(draw_no)
    if draw is None:
        draw = fetch_draw_info(draw_no)

    # evaluate_ticket does validation/sorting for us
    evaluation = evaluate_ticket(draw, numbers)
    now = datetime.now(timezone.utc)

    collection = _user_ticket_collection()
    document = collection.find_one_and_update(
        {"user_id": user_id, "draw_no": draw_no, "numbers": evaluation["numbers"]},
        {
            "$set": {
                "user_id": user_id,
                "draw_no": draw_no,
                "numbers": evaluation["numbers"],
                "evaluation": evaluation,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if not document:
        raise UserTicketError("티켓 정보를 저장하지 못했습니다.")

    return {
        "id": str(document["_id"]),
        "userId": document["user_id"],
        "draw_no": document["draw_no"],
        "numbers": document["numbers"],
        "created_at": document.get("created_at"),
        "evaluation": document.get("evaluation", evaluation),
    }


__all__ = ["save_user_ticket", "get_user_tickets", "UserTicketError"]


def get_user_tickets(user_id: str) -> List[Dict[str, object]]:
    if not user_id:
        raise UserTicketError("userId가 비어 있습니다.")

    collection = _user_ticket_collection()
    cursor = collection.find({"user_id": user_id}).sort("created_at", -1)

    results: List[Dict[str, object]] = []
    for document in cursor:
        results.append(
            {
                "id": str(document["_id"]),
                "userId": document["user_id"],
                "draw_no": document["draw_no"],
                "numbers": document["numbers"],
                "created_at": document.get("created_at"),
                "evaluation": document.get("evaluation", {}),
            }
        )
    return results
