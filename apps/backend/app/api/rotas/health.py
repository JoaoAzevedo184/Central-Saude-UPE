import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.api.problemas import erros

logger = logging.getLogger(__name__)
router = APIRouter(tags=["saude"])


@router.get("/health", responses=erros(503))
def health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("health: banco indisponível (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.") from None
    return {"status": "ok"}
