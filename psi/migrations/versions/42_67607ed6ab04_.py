""" Add create_date field to product and set value for existing products.

Revision ID: 67607ed6ab04
Revises: b9dc56c47ef4
Create Date: 2017-06-27 22:46:44.079629

"""

from datetime import datetime
from alembic import op
from sqlalchemy import func
from sqlalchemy.sql import text
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '67607ed6ab04'
down_revision = 'b9dc56c47ef4'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('product', sa.Column('create_date', sa.DateTime(), nullable=True))

    results = op.get_bind().execute(text("""
    select prd.id, min(po.order_date) from purchase_order po, product prd, purchase_order_line pol
    where pol.product_id = prd.id and po.id = pol.purchase_order_id
    group by prd.id
    """)).fetchall()
    for r in results:
        sup_id = r[0]
        po_date = r[1]
        sql = "update product set create_date = '{0}' where id={1}".format(po_date, sup_id)
        op.get_bind().execute(text(sql))

    results = op.get_bind().execute(text("""
    select p.id, min(so.order_date) from sales_order so, sales_order_line sol,
    product p where so.id = sol.sales_order_id and
    sol.product_id = p.id group by p.id;
    """)).fetchall()
    for r in results:
        sup_id = r[0]
        so_date = r[1]
        sql = "update product set create_date = '{0}' where id={1} and create_date is null".format(so_date, sup_id)
        op.get_bind().execute(text(sql))

    op.get_bind().execute(text("update product set create_date = '{0}' where create_date is null".format(datetime.now())))
    op.alter_column('product', 'create_date', existing_type=sa.DateTime(), nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('product', 'create_date')
    # ### end Alembic commands ###