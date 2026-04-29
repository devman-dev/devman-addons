from unittest.mock import Mock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPfGatewayCompanyMembership(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Membership = cls.env["pf.gateway.company.membership"]
        cls.Company = cls.env["pf.gateway.company"]
        cls.User = cls.env["pf.gateway.user"]
        cls.BankAccount = cls.env["pf.gateway.bank.account"]
        cls.env["ir.config_parameter"].sudo().set_param("pagoflex_wallet_gateway.base_url", "https://gateway.test")
        cls.env["ir.config_parameter"].sudo().set_param("pagoflex_wallet_gateway.api_key", "secret-api-key")
        cls.env["ir.config_parameter"].sudo().set_param("pagoflex_wallet_gateway.page_size", "2")

        cls.company_partner = cls.env["res.partner"].create(
            {"name": "Acme SA", "company_type": "company", "is_company": True, "vat": "30-12345678-9"}
        )
        cls.user_partner = cls.env["res.partner"].create({"name": "User One", "email": "user@example.com"})
        cls.company = cls.Company.with_context(skip_gateway_company_push=True).create(
            {
                "name": "Acme SA",
                "external_id": "company-1",
                "partner_id": cls.company_partner.id,
                "cuit": "30-12345678-9",
            }
        )
        cls.user = cls.User.create(
            {
                "external_id": "user-1",
                "partner_id": cls.user_partner.id,
                "email": "user@example.com",
                "full_name": "User One",
            }
        )
        cls.bank_account = cls.BankAccount.create(
            {
                "external_id": "bank-1",
                "gateway_user_id": cls.user.id,
                "cvu_cbu": "0000003100012345678901",
            }
        )

    def _membership_payload(self, **overrides):
        payload = {
            "id": "membership-1",
            "company_id": "company-1",
            "company_name": "Acme SA",
            "company_cuit": "30123456789",
            "user_id": "user-1",
            "user_email": "user@example.com",
            "bank_account_id": "bank-1",
            "bank_account_cvu_cbu": "0000003100012345678901",
            "role": "owner",
            "is_active": True,
            "created_at": "2026-04-28T10:00:00Z",
            "updated_at": "2026-04-28T11:00:00Z",
        }
        payload.update(overrides)
        return payload

    def test_values_from_gateway_item_maps_remote_fields(self):
        values = self.Membership._values_from_gateway_item(self._membership_payload())

        self.assertEqual(values["external_id"], "membership-1")
        self.assertEqual(values["company_id"], self.company.id)
        self.assertEqual(values["user_id"], self.user.id)
        self.assertEqual(values["bank_account_id"], self.bank_account.id)
        self.assertEqual(values["company_cuit"], "30123456789")
        self.assertEqual(values["role"], "owner")
        self.assertTrue(values["active"])

    def test_paginated_get_uses_limit_offset_and_extra_filters(self):
        calls = []

        def fake_request(recordset, method, path, params=None, payload=None):
            calls.append(dict(params))
            items = [{"id": "1"}, {"id": "2"}] if params["offset"] == 0 else [{"id": "3"}]
            return {"items": items, "total": 3, "limit": params["limit"], "offset": params["offset"]}

        with patch.object(type(self.Membership), "_gateway_request_json", fake_request):
            items = self.Membership._gateway_paginated_get(
                "/admin/gateway/company-memberships",
                extra_params={"owner_cuit": "30-12345678-9", "is_active": True},
            )

        self.assertEqual([item["id"] for item in items], ["1", "2", "3"])
        self.assertEqual(calls[0]["limit"], 2)
        self.assertEqual(calls[0]["offset"], 0)
        self.assertEqual(calls[1]["offset"], 2)
        self.assertEqual(calls[0]["owner_cuit"], "30-12345678-9")
        self.assertTrue(calls[0]["is_active"])

    def test_upsert_updates_existing_record_and_user_shortcut(self):
        record = self.Membership._upsert_gateway_item(self._membership_payload(role="admin"))
        same_record = self.Membership._upsert_gateway_item(self._membership_payload(role="member"))

        self.assertEqual(record, same_record)
        self.assertEqual(same_record.role, "member")
        self.assertEqual(self.user.parent_company_gateway_user_id, self.company)
        self.assertEqual(self.user.cuit_owner, "30123456789")

    def test_current_backend_uniqueness_deactivates_previous_active_membership(self):
        first = self.Membership._upsert_gateway_item(self._membership_payload(id="membership-1"))
        second = self.Membership._upsert_gateway_item(self._membership_payload(id="membership-2"))

        self.assertFalse(first.active)
        self.assertTrue(second.active)

    def test_gateway_http_error_raises_user_error_without_secret(self):
        response = Mock(status_code=401, text="invalid api key", reason="Unauthorized")

        with patch("requests.request", return_value=response):
            with self.assertRaises(UserError) as error:
                self.Membership._gateway_request_json("GET", "/admin/gateway/company-memberships")

        self.assertIn("401", str(error.exception))
        self.assertNotIn("secret-api-key", str(error.exception))
