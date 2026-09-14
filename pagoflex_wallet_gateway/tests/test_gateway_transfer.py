from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPfGatewayTransfer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BankAccount = cls.env["pf.gateway.bank.account"]
        cls.User = cls.env["pf.gateway.user"]
        cls.Transfer = cls.env["pf.gateway.transfer"]

    def test_app_search_filter_uses_dashboard_app_normalization(self):
        account = self.BankAccount.create(
            {
                "external_id": "bank-pf-1",
                "cvu_cbu": "0000003100012345678901",
                "app": " PagoFlex ",
            }
        )
        transfer = self.Transfer.create(
            {
                "external_id": "transfer-pf-1",
                "movement_nature": "TRANSFER",
                "status": "COMPLETED",
                "amount": 100.0,
                "source_address": "0000003100099999999999",
                "destination_address": account.cvu_cbu,
            }
        )

        records = self.Transfer.search(
            [
                ("is_external_incoming_transfer", "=", True),
                ("is_pagoflex_wallet_transfer", "=", True),
            ]
        )

        self.assertIn(transfer, records)

    def test_sivep_search_filter_includes_sivep_accounts(self):
        account = self.BankAccount.create(
            {
                "external_id": "bank-sv-1",
                "cvu_cbu": "000053880100000047013",
                "app": "sivep",
            }
        )
        transfer = self.Transfer.create(
            {
                "external_id": "transfer-sv-1",
                "movement_nature": "TRANSFER",
                "status": "COMPLETED",
                "amount": 125.60,
                "source_address": "0720520088000035088390",
                "destination_address": account.cvu_cbu,
            }
        )

        records = self.Transfer.search(
            [
                ("is_external_incoming_transfer", "=", True),
                ("is_sivep_wallet_transfer", "=", True),
            ]
        )

        self.assertIn(transfer, records)

    def test_external_outgoing_search_filter_matches_wallet_source(self):
        account = self.BankAccount.create(
            {
                "external_id": "bank-pf-out-1",
                "cvu_cbu": "0000003100012345678902",
                "app": "pagoflex",
            }
        )
        transfer = self.Transfer.create(
            {
                "external_id": "transfer-pf-out-1",
                "movement_nature": "TRANSFER",
                "status": "COMPLETED",
                "amount": 80.0,
                "source_address": account.cvu_cbu,
                "destination_address": "0000003100099999999998",
            }
        )

        records = self.Transfer.search(
            [
                ("is_external_outgoing_transfer", "=", True),
                ("is_pagoflex_wallet_transfer", "=", True),
            ]
        )

        self.assertIn(transfer, records)

    def test_user_cuit_cuil_or_dni_uses_dni_fallback(self):
        user_with_cuit = self.User.create(
            {
                "external_id": "user-cuit-1",
                "gateway_display_name": "Alias Comercial",
                "full_name": "Usuario Con Cuit",
                "cuit_cuil": "20-12345678-9",
                "dni": "12345678",
            }
        )
        user_without_cuit = self.User.create(
            {
                "external_id": "user-dni-1",
                "full_name": "Usuario Sin Cuit",
                "dni": "87654321",
            }
        )
        transfer = self.Transfer.create(
            {
                "external_id": "transfer-user-doc-1",
                "movement_nature": "TRANSFER",
                "status": "COMPLETED",
                "amount": 50.0,
                "source_user_id": user_with_cuit.id,
                "destination_user_id": user_without_cuit.id,
            }
        )

        self.assertEqual(user_with_cuit.cuit_cuil_or_dni, "20-12345678-9")
        self.assertEqual(user_without_cuit.cuit_cuil_or_dni, "87654321")
        self.assertEqual(user_with_cuit.cuit_cuil_or_dni_display, "20-12345678-9 - Usuario Con Cuit")
        self.assertEqual(user_without_cuit.cuit_cuil_or_dni_display, "87654321 - Usuario Sin Cuit")
        self.assertEqual(transfer.source_user_cuit_cuil_or_dni, "20-12345678-9")
        self.assertEqual(transfer.destination_user_cuit_cuil_or_dni, "87654321")
        self.assertEqual(
            transfer.source_user_cuit_cuil_or_dni_display,
            "20-12345678-9 - Usuario Con Cuit",
        )
        self.assertEqual(
            transfer.destination_user_cuit_cuil_or_dni_display,
            "87654321 - Usuario Sin Cuit",
        )
