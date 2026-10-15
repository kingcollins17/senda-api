"""Cascade deletes through wallets and wallet accounts.

Revision ID: 0002_wallet_foreign_key_cascade
Revises: 0001_wallet_user_unique
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_wallet_foreign_key_cascade"
down_revision = "0001_wallet_user_unique"
branch_labels = None
depends_on = None


def _set_cascade_foreign_key(
    table_name: str,
    constrained_column: str,
    referred_table: str,
    referred_column: str,
    constraint_name: str,
) -> None:
    bind = op.get_bind()
    foreign_keys = sa.inspect(bind).get_foreign_keys(table_name)
    matching = [
        foreign_key
        for foreign_key in foreign_keys
        if foreign_key.get("constrained_columns") == [constrained_column]
        and foreign_key.get("referred_table") == referred_table
        and foreign_key.get("referred_columns") == [referred_column]
    ]

    if any(
        str(foreign_key.get("options", {}).get("ondelete", "")).upper() == "CASCADE"
        for foreign_key in matching
    ):
        return

    for foreign_key in matching:
        old_name = foreign_key.get("name")
        if not old_name:
            raise RuntimeError(
                f"Cannot replace unnamed foreign key on {table_name}.{constrained_column}; "
                "assign it a name before applying this migration."
            )
        op.drop_constraint(old_name, table_name, type_="foreignkey")

    op.create_foreign_key(
        constraint_name,
        table_name,
        referred_table,
        [constrained_column],
        [referred_column],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    _set_cascade_foreign_key(
        "wallets", "user_id", "users", "id", "fk_wallets_user_id_users"
    )
    _set_cascade_foreign_key(
        "wallet_accounts",
        "wallet_id",
        "wallets",
        "id",
        "fk_wallet_accounts_wallet_id_wallets",
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, constraint_name in (
        ("wallet_accounts", "fk_wallet_accounts_wallet_id_wallets"),
        ("wallets", "fk_wallets_user_id_users"),
    ):
        existing_names = {
            foreign_key.get("name")
            for foreign_key in sa.inspect(bind).get_foreign_keys(table_name)
        }
        if constraint_name in existing_names:
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")

    op.create_foreign_key(
        "fk_wallet_accounts_wallet_id_wallets",
        "wallet_accounts",
        "wallets",
        ["wallet_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_wallets_user_id_users",
        "wallets",
        "users",
        ["user_id"],
        ["id"],
    )