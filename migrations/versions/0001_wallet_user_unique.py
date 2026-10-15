"""Enforce one wallet per user.

Revision ID: 0001_wallet_user_unique
Revises:
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_wallet_user_unique"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_constraints = sa.inspect(bind).get_unique_constraints("wallets")
    if any(
        constraint.get("name") == "uq_wallets_user_id"
        and constraint.get("column_names") == ["user_id"]
        for constraint in existing_constraints
    ):
        return

    duplicates = bind.execute(
        sa.text(
            "SELECT user_id, COUNT(*) AS wallet_count "
            "FROM wallets GROUP BY user_id HAVING COUNT(*) > 1"
        )
    ).all()
    if duplicates:
        users = ", ".join(str(row.user_id) for row in duplicates)
        raise RuntimeError(
            "Cannot add uq_wallets_user_id: multiple wallets exist for user(s): "
            f"{users}. Resolve these duplicate wallet rows, then rerun the migration."
        )

    op.create_unique_constraint("uq_wallets_user_id", "wallets", ["user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_wallets_user_id", "wallets", type_="unique")