"""add photo

Revision ID: 182768f463c9
Revises: 80df69a32014
Create Date: 2017-05-03 16:44:29.820000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '182768f463c9'
down_revision = '80df69a32014'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('photo', sa.String(length=64), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'photo')
    # ### end Alembic commands ###