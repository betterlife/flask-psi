from __future__ import print_function
import unittest
from datetime import datetime

from tests import fixture
import app.const as const


class TestReceiving(unittest.TestCase):
    def setUp(self):
        self.app = fixture.init_app()
        self.test_client = self.app.test_client()
        self.app_context = self.app.test_request_context()
        self.app_context.push()

    def tearDown(self):
        fixture.cleanup_database(self.app_context)
        self.app_context.pop()

    def test_get_by_po_id(self):
        from app.models.receiving import Receiving
        from app.models.enum_values import EnumValues
        from app.service import Info
        from tests.object_faker import object_faker

        def test_logic():
            po = object_faker.purchase_order()
            po.status = EnumValues.find_one_by_code(const.PO_RECEIVED_STATUS_KEY)
            receiving = Receiving()
            receiving.purchase_order = po
            receiving.date = datetime.now()
            receiving.status = EnumValues.find_one_by_code(const.RECEIVING_DRAFT_STATUS_KEY)
            db = Info.get_db()

            db.session.add(po)
            db.session.add(receiving)
            db.session.commit()
            receiving_returned = receiving.filter_by_po_id(1)[0]
            self.assertEqual(receiving, receiving_returned)

        from tests.fixture import run_as_admin
        run_as_admin(self.test_client, test_logic)

    def test_create_draft_recv_from_po(self):
        from app.models.receiving import Receiving
        from tests.object_faker import object_faker
        import app.const as const

        def test_logic():
            po = object_faker.purchase_order(number_of_line=2)
            receiving = Receiving.create_draft_recv_from_po(po)
            self.assertEquals(po, receiving.purchase_order)
            self.assertEquals(len(po.lines), len(receiving.lines))
            self.assertEquals(len(po.lines), len(receiving.inventory_transaction.lines))
            self.assertEquals(po.order_date, receiving.date)
            self.assertEquals(receiving.status.code, const.RECEIVING_DRAFT_STATUS_KEY)
            self.assertEquals(po.supplier, receiving.supplier)
            self.assertEquals(receiving.inventory_transaction.date, po.order_date)
            self.assertEquals(receiving.inventory_transaction.type.code, const.PURCHASE_IN_INV_TRANS_KEY)
            self.assertIsNotNone(receiving.inventory_transaction)
            for line in receiving.lines:
                self.assertIsNotNone(line)
                self.assertIsNotNone(line.purchase_order_line)
                self.assertIsNotNone(line.inventory_transaction_line)
                self.assertEquals(line.quantity, line.purchase_order_line.quantity)
                self.assertEquals(line.price, line.purchase_order_line.unit_price)
                self.assertEquals(line.product, line.purchase_order_line.product)
                self.assertEquals(line.inventory_transaction_line.in_transit_quantity, line.quantity)
                self.assertEquals(line.inventory_transaction_line.product, line.product)
                self.assertEquals(line.inventory_transaction_line.price, line.price)

        from tests.fixture import run_as_admin
        run_as_admin(self.test_client, test_logic)
