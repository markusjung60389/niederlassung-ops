"""user administration: roles with descriptions and the local password login

Revision ID: 0006_accounts
Revises: 0005_branches
Create Date: 2026-08-09

Additive only - columns, no drops, no deletions.

1. `roles` gains a description and a `system` flag. The four presets are marked
   system: they are kept in sync with `permissions.ROLE_PRESETS` on every start,
   which is exactly why they must not be editable in the user administration.
   Every existing role is a preset, so the flag is set for all of them.
2. `users` gains everything the local password login needs: the hash, whether
   the password still has to be changed, the last login, the failed-attempt
   counter with its lockout, and a token version.

`token_version` starts at 1 rather than 0 so a token minted before this
migration - there are none, but the invariant is cheap - can never match.

No password is set here. The emergency administrator is created by the seed on
the next start, and only when the installation has none; see `app/seed.py`.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_accounts"
down_revision: Union[str, None] = "0005_branches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("system", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="1")
        )

    # Everything that exists at this point is one of the four presets.
    op.execute(sa.text("UPDATE roles SET system = true"))


def downgrade() -> None:
    # Passwords disappear with the column. That is the point of going back:
    # the local login is gone, Entra ID remains, and no hash is left behind.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("token_version")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_count")
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("password_changed_at")
        batch_op.drop_column("must_change_password")
        batch_op.drop_column("password_hash")

    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.drop_column("system")
        batch_op.drop_column("description")
