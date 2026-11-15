# DVO-L3-7F2A91
"""Wait for PostgreSQL, optionally requiring all Alembic migrations."""
import asyncio
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.session import engine


async def main():
    expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
    try:
        for attempt in range(120):
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                    if "--schema" in sys.argv:
                        result = await connection.execute(
                            text("SELECT version_num FROM alembic_version")
                        )
                        if set(result.scalars()) != expected:
                            raise RuntimeError("Migrations are not complete")
                print("Database ready", flush=True)
                return
            except Exception as exc:
                print(
                    f"Waiting for database ({attempt + 1}): {type(exc).__name__}",
                    flush=True,
                )
                await asyncio.sleep(2)
        raise RuntimeError("Database readiness timed out")
    finally:
        await engine.dispose()


asyncio.run(main())
