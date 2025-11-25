"""empty message

Revision ID: 65c6b95d9dbf
Revises: cc2f8cdded50
Create Date: 2025-11-25 14:24:59.620374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65c6b95d9dbf'
down_revision: Union[str, Sequence[str], None] = 'cc2f8cdded50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
