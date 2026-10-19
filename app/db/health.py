from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter()


@router.get("/ready")
async def readiness() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
