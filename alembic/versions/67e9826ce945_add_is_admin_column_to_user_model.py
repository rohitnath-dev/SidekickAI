"""add is_admin column to user model

Revision ID: 67e9826ce945
Revises: 
Create Date: 2026-08-04 11:17:35.322982

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67e9826ce945'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column is_admin to table users
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=False))

def downgrade() -> None:
    # Drop column is_admin from table users
    op.drop_column('users', 'is_admin')
