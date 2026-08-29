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
    # Add column is_admin to table users if not already present
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'users' in tables:
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'is_admin' not in columns:
            op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    else:
        op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=False))

def downgrade() -> None:
    # Drop column is_admin from table users if present
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'users' in tables:
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'is_admin' in columns:
            op.drop_column('users', 'is_admin')
