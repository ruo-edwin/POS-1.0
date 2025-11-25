"""update models

Revision ID: b5b6842e6382
Revises: 65c6b95d9dbf
Create Date: 2025-11-25 14:26:02.335412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5b6842e6382'
down_revision: Union[str, Sequence[str], None] = '65c6b95d9dbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
