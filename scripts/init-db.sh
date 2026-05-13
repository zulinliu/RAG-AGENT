#!/usr/bin/env bash
#
# Initialize PostgreSQL database:
#   1. Wait for PostgreSQL to accept connections
#   2. Run Alembic migrations
#   3. Create default admin user (if not exists)
#
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-rag_agent}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

# Admin user defaults
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

echo "[init-db] Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."

# Wait for PostgreSQL to be ready
MAX_RETRIES=30
RETRY=0
until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -q 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "${RETRY}" -ge "${MAX_RETRIES}" ]; then
        echo "[init-db] ERROR: PostgreSQL not reachable after ${MAX_RETRIES} retries." >&2
        exit 1
    fi
    echo "[init-db] Retry ${RETRY}/${MAX_RETRIES} ..."
    sleep 2
done
echo "[init-db] PostgreSQL is ready."

# Run Alembic migrations
echo "[init-db] Running Alembic migrations ..."
cd /app
alembic upgrade head
echo "[init-db] Alembic migrations applied."

# Create default admin user via the application's CLI
echo "[init-db] Creating default admin user (if not exists) ..."
python - <<'PYEOF'
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init-db")

async def create_admin():
    # Import here so Alembic migrations have already run
    from sqlalchemy import select
    from app.models.database import get_session, init_engine
    from app.models.user import User
    from app.utils.security import hash_password

    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")

    async for session in get_session():
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Admin user '%s' already exists, skipping.", email)
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name="System Admin",
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        logger.info("Admin user '%s' created.", email)

import asyncio
asyncio.run(create_admin())
PYEOF

echo "[init-db] Done."
