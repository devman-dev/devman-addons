from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIncomingTransferCommissionSettings(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env["pf.gateway.incoming.transfer.commission.settings"]
        cls.BankAccount = cls.env["pf.gateway.bank.account"]
        cls.CommissionAccount = cls.env["pf.gateway.incoming.transfer.commission.account"]

        cls.setting = cls.Settings.with_context(skip_gateway_push=True).create(
            {
                "name": "Comision test-propagation-only",
                "gateway_setting_id": 10,
                "app_name": "test-propagation-only",
                "default_percentage": 8.0,
                "settlement_cvu": "0000538801000000044014",
                "is_active": True,
            }
        )

        cls.bank_a = cls.BankAccount.create(
            {
                "external_id": "bank-a",
                "cvu_cbu": "0000538801000000064016",
                "app": "test-propagation-only",
            }
        )
        cls.bank_b = cls.BankAccount.create(
            {
                "external_id": "bank-b",
                "cvu_cbu": "0000538801000000051016",
                "app": "test-propagation-only",
            }
        )
        cls.BankAccount.create(
            {
                "external_id": "bank-other",
                "cvu_cbu": "4320001010003138730019",
                "app": "pagoflex",
            }
        )

        cls.CommissionAccount.create(
            {
                "external_id": "comm-a",
                "bank_account_external_id": "bank-a",
                "cvu_cbu": "0000538801000000064016",
                "commission_percentage": 10.0,
                "is_active": True,
            }
        )
        cls.CommissionAccount.create(
            {
                "external_id": "comm-b",
                "bank_account_external_id": "bank-b",
                "cvu_cbu": "0000538801000000051016",
                "commission_percentage": 2.0,
                "is_active": True,
            }
        )

    def test_write_default_percentage_propagates_minimum_to_app_accounts(self):
        account_calls = []

        def fake_gateway_request(recordset, method, path, params=None, payload=None):
            if path == "/admin/gateway/incoming-transfer-commission/settings":
                return {
                    "id": 10,
                    "app_name": payload.get("app_name"),
                    "default_percentage": payload.get("default_percentage"),
                    "settlement_bank_account_id": "settlement-bank-1",
                    "settlement_cvu": payload.get("settlement_cvu"),
                    "is_active": payload.get("is_active", True),
                }

            if path == "/admin/gateway/incoming-transfer-commission/accounts":
                account_calls.append({"params": params or {}, "payload": payload or {}})
                return {
                    "id": f"remote-{payload.get('cvu_cbu')}",
                    "bank_account_id": False,
                    "cvu_cbu": payload.get("cvu_cbu"),
                    "commission_percentage": payload.get("commission_percentage"),
                    "is_active": payload.get("is_active", True),
                }

            raise AssertionError(f"Unexpected gateway path: {path}")

        setting = self.Settings.browse(self.setting.id)
        with patch.object(type(self.Settings), "_gateway_request_json", fake_gateway_request):
            setting.write({"default_percentage": 4.0})

        self.assertEqual(len(account_calls), 2)
        for call in account_calls:
            self.assertEqual(call["params"].get("app_name"), "test-propagation-only")

        updated_a = self.CommissionAccount.search([("cvu_cbu", "=", "0000538801000000064016")], limit=1)
        updated_b = self.CommissionAccount.search([("cvu_cbu", "=", "0000538801000000051016")], limit=1)

        self.assertEqual(updated_a.commission_percentage, 4.0)
        self.assertEqual(updated_b.commission_percentage, 2.0)
