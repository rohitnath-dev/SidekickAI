"""add telegram and discord to messagesource enum

Revision ID: 76d48842aa6f
Revises: 67e9826ce945
Create Date: 2026-08-04 13:07:09.174703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76d48842aa6f'
down_revision: Union[str, Sequence[str], None] = '67e9826ce945'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if we are running on PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Commit the active transaction first to allow ALTER TYPE ... ADD VALUE
        op.execute("COMMIT")
        op.execute("ALTER TYPE messagesource ADD VALUE IF NOT EXISTS 'TELEGRAM'")
        op.execute("ALTER TYPE messagesource ADD VALUE IF NOT EXISTS 'DISCORD'")

def downgrade() -> None:
    pass
