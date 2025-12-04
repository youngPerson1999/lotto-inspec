"""Service helpers to store user-submitted Lotto tickets and their outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_scope
from app.models.tables import UserTicketORM
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


def _ensure_database_backend() -> None:
    if not get_settings().use_database_storage:
        raise UserTicketError(
            "MariaDB 백엔드에서만 사용자 티켓 저장이 가능합니다. "
            "LOTTO_STORAGE_BACKEND=mariadb 환경을 설정하세요.",
        )


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
    _ensure_database_backend()
    draw = None
    if settings.use_database_storage:
        draw = get_stored_draw(draw_no)
    if draw is None:
        draw = fetch_draw_info(draw_no)

    # evaluate_ticket does validation/sorting for us
    evaluation = evaluate_ticket(draw, numbers)
    now = datetime.now(timezone.utc)

    with session_scope() as session:
        record = UserTicketORM(
            user_id=user_id,
            draw_no=draw_no,
            numbers=evaluation["numbers"],
            evaluation=evaluation,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.flush()

        return {
            "id": str(record.id),
            "userId": record.user_id,
            "draw_no": record.draw_no,
            "numbers": record.numbers,
            "created_at": record.created_at,
            "evaluation": record.evaluation,
        }


__all__ = ["save_user_ticket", "get_user_tickets", "UserTicketError"]


def get_user_tickets(user_id: str) -> List[Dict[str, object]]:
    if not user_id:
        raise UserTicketError("userId가 비어 있습니다.")

    _ensure_database_backend()

    with session_scope() as session:
        rows = session.scalars(
            select(UserTicketORM)
            .where(UserTicketORM.user_id == user_id)
            .order_by(UserTicketORM.created_at.desc())
        ).all()

    results: List[Dict[str, object]] = []
    for row in rows:
        results.append(
            {
                "id": str(row.id),
                "userId": row.user_id,
                "draw_no": row.draw_no,
                "numbers": row.numbers,
                "created_at": row.created_at,
                "evaluation": row.evaluation or {},
            }
        )
    return results
