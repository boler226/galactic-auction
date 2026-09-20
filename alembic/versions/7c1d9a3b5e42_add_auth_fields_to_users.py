"""add auth fields to users (password hash, role, is_active)

Revision ID: 7c1d9a3b5e42
Revises: 614047abe21d
Create Date: 2026-09-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7c1d9a3b5e42"
down_revision = "614047abe21d"
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("admin", "user", name="user_role", create_type=False)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)

    # Pre-existing rows (if any) get an empty hash that can never match a
    # password, so such accounts simply can not log in until a reset.
    op.add_column(
        "users",
        sa.Column(
            "hashed_password", sa.String(length=255), nullable=False, server_default=""
        ),
    )
    op.alter_column("users", "hashed_password", server_default=None)

    op.add_column(
        "users",
        sa.Column("role", user_role, nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
    op.drop_column("users", "hashed_password")
    user_role.drop(op.get_bind(), checkfirst=True)
