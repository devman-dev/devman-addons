from datetime import date, datetime

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPfReconciliationControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BankAccount = cls.env["pf.gateway.bank.account"]
        cls.Transfer = cls.env["pf.gateway.transfer"]
        cls.BankMovement = cls.env["pf.gateway.bank.movement"]
        cls.Reconciliation = cls.env["pf.reconciliation.control"].with_context(tz="America/Buenos_Aires")

        cls.account = cls.BankAccount.create(
            {
                "external_id": "bank-recon-1",
                "cvu_cbu": "0000538801000000144011",
                "app": "pagoflex",
                "status": "active",
            }
        )

    def test_night_window_counts_transfer_by_transaction_local_date_and_time(self):
        self.Transfer.create(
            {
                "external_id": "transfer-recon-123000",
                "movement_nature": "TRANSFER",
                "status": "COMPLETED",
                "amount": 123000.0,
                "currency": "ARS",
                "source_address": "0000003100017758307165",
                "destination_address": self.account.cvu_cbu,
                "destination_bank_account_id": self.account.id,
                "fecha_negocio": date(2026, 6, 10),
                "transaction_at": datetime(2026, 6, 10, 1, 28, 0),
            }
        )
        self.Reconciliation._process_day_windows(date(2026, 6, 9))

        night = self.Reconciliation.search(
            [("date", "=", date(2026, 6, 9)), ("time_window", "=", "21_24")],
            limit=1,
        )
        self.assertEqual(night.wallet_in_count, 1)
        self.assertEqual(night.wallet_in_amount, 123000.0)
        self.assertEqual(night.bank_in_count, 0)
        self.assertEqual(night.bank_in_amount, 0.0)

        self.Reconciliation._process_day_windows(date(2026, 6, 10))
        next_day_night = self.Reconciliation.search(
            [("date", "=", date(2026, 6, 10)), ("time_window", "=", "21_24")],
            limit=1,
        )
        self.assertEqual(next_day_night.wallet_in_count, 0)

    def test_night_window_counts_bank_movement_by_movement_datetime(self):
        self.BankMovement.create(
            {
                "cbu_cvu_alias": self.account.cvu_cbu,
                "movement_id": "movement-recon-123000",
                "movement_date": date(2026, 6, 10),
                "movement_time": "01:28:00",
                "concept": "Transferencia",
                "debit_credit": "C",
                "currency": "ARS",
                "amount": 123000.0,
                "movement_nature": "TRANSFER",
                "movement_direction": "INCOMING",
            }
        )

        self.Reconciliation._process_day_windows(date(2026, 6, 9))

        night = self.Reconciliation.search(
            [("date", "=", date(2026, 6, 9)), ("time_window", "=", "21_24")],
            limit=1,
        )
        self.assertEqual(night.bank_in_count, 1)
        self.assertEqual(night.bank_in_amount, 123000.0)

        self.Reconciliation._process_day_windows(date(2026, 6, 10))
        next_day_night = self.Reconciliation.search(
            [("date", "=", date(2026, 6, 10)), ("time_window", "=", "21_24")],
            limit=1,
        )
        self.assertEqual(next_day_night.bank_in_count, 0)
