"""add subscription_window scheme_name and evidence

Revision ID: a78332b365e2
Revises: c14df8b4b881
Create Date: 2026-09-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a78332b365e2'
down_revision = 'c14df8b4b881'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('subscription_window', sa.Column('scheme_name', sa.String(), nullable=True))
    op.add_column('subscription_window', sa.Column('evidence', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('subscription_window', 'evidence')
    op.drop_column('subscription_window', 'scheme_name')
