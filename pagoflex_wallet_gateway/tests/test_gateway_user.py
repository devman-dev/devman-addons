from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPfGatewayUser(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.User = cls.env["pf.gateway.user"]
        cls.env["ir.config_parameter"].sudo().set_param("pagoflex_wallet_gateway.base_url", "https://gateway.test")
        cls.env["ir.config_parameter"].sudo().set_param("pagoflex_wallet_gateway.api_key", "secret-api-key")

        cls.user = cls.User.with_context(skip_gateway_user_push=True).create(
            {
                "external_id": "user-1",
                "email": "user@example.com",
                "gateway_display_name": "Nombre original",
                "full_name": "Usuario Uno",
                "first_name": "Usuario",
                "last_name": "Uno",
                "cuit_cuil": "20123456789",
            }
        )

    def test_write_keeps_display_name_when_gateway_response_omits_it(self):
        def fake_gateway_request(recordset, method, path, params=None, payload=None):
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/admin/gateway/users")
            self.assertEqual(payload["email"], "nuevo@example.com")
            self.assertEqual(payload["display_name"], "Nombre original")
            return {
                "id": "user-1",
                "email": payload["email"],
                "full_name": "Usuario Uno",
                "first_name": "Usuario",
                "last_name": "Uno",
                "cuit_cuil": "20123456789",
            }

        user = self.User.browse(self.user.id)
        with patch.object(type(self.User), "_gateway_request_json", fake_gateway_request):
            user.write({"email": "nuevo@example.com"})

        user.invalidate_recordset()
        self.assertEqual(user.gateway_display_name, "Nombre original")
        self.assertEqual(user.name, "Nombre original")

    def test_create_truncates_long_names_before_sending_to_gateway(self):
        display_name = "A" * 60
        full_name = "B" * 60

        def fake_gateway_request(recordset, method, path, params=None, payload=None):
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/admin/gateway/users")
            self.assertEqual(payload["display_name"], display_name[:50])
            self.assertEqual(payload["full_name"], full_name[:50])
            return {
                "id": "created-user",
                "email": "created@example.com",
                "display_name": payload["display_name"],
                "full_name": payload["full_name"],
            }

        with patch.object(type(self.User), "_gateway_request_json", fake_gateway_request):
            self.User.create(
                {
                    "external_id": False,
                    "email": "created@example.com",
                    "gateway_display_name": display_name,
                    "full_name": full_name,
                }
            )