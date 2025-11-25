"""update models

Revision ID: cc2f8cdded50
Revises: 
Create Date: 2025-11-25 14:03:21.624472

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cc2f8cdded50'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add buying_price column to products table
    op.add_column('products', sa.Column('buying_price', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove buying_price column if downgrading
    op.drop_column('products', 'buying_price')
