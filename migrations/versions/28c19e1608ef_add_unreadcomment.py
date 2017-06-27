"""add unreadcomment

Revision ID: 28c19e1608ef
Revises: 487b255a18d4
Create Date: 2017-06-26 11:14:01.296000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '28c19e1608ef'
down_revision = '487b255a18d4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comments', sa.Column('confirmed', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comments', 'confirmed')
    # ### end Alembic commands ###