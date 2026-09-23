# -*- coding: utf-8 -*-
"""
Portal Club Support -- JogaJunto
Controladores del portal: registro publico, seleccion de clubes, dashboard.
"""

import base64 as _b64
from datetime import date, datetime

from odoo import http, fields, _
import logging
_logger = logging.getLogger(__name__)
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class PortalClubSupport(CustomerPortal):

    # --------------------------------------------------
    # REGISTRO PUBLICO -- Step 1: Seus dados
    # --------------------------------------------------
    @http.route("/club-support/register", type="http", auth="public", website=True, sitemap=False)
    def club_support_register(self, **kw):
        """Pagina publica de registro. GET muestra formulario, POST crea cuenta."""
        if request.env.user and request.env.user.id != request.env.ref("base.public_user").id:
            return request.redirect("/my/club-support")

        if request.httprequest.method == "POST":
            return self._handle_register_post(**kw)

        return request.render("portal_club_support.jj_register_page", {"title": "JogaJunto — Cadastro"})

    def _handle_register_post(self, **kw):
        """Procesa el POST del formulario de registro publico."""
        name = (kw.get("name") or "").strip()
        email = (kw.get("email") or "").strip().lower()
        cpf = (kw.get("cpf") or "").strip()
        birth_date = kw.get("birth_date", "").strip()
        telefone = (kw.get("telefone") or "").strip()
        password = kw.get("password", "").strip()
        age_confirmed = kw.get("age_confirmed") == "on"

        # Validaciones server-side
        if not name or not email or not password:
            return request.render("portal_club_support.jj_register_page", {
                "name": name,
                "email": email,
                "cpf": cpf,
                "birth_date": birth_date,
                "telefone": telefone,
                "error": "Nome, e-mail e senha sao obrigatorios.",
            })

        if len(password) < 6:
            return request.render("portal_club_support.jj_register_page", {
                "name": name,
                "email": email,
                "cpf": cpf,
                "birth_date": birth_date,
                "telefone": telefone,
                "error": "A senha deve ter no minimo 6 caracteres.",
            })

        if not age_confirmed:
            return request.render("portal_club_support.jj_register_page", {
                "name": name,
                "email": email,
                "cpf": cpf,
                "birth_date": birth_date,
                "telefone": telefone,
                "error": "Voce precisa confirmar que tem mais de 18 anos.",
            })

        try:
            parsed_birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return request.render("portal_club_support.jj_register_page", {
                "name": name, "email": email, "cpf": cpf,
                "birth_date": birth_date, "telefone": telefone,
                "error": "Informe uma data de nascimento valida.",
            })
        today = date.today()
        age = today.year - parsed_birth_date.year - (
            (today.month, today.day) <
            (parsed_birth_date.month, parsed_birth_date.day)
        )
        if age < 18:
            return request.render("portal_club_support.jj_register_page", {
                "name": name, "email": email, "cpf": cpf,
                "birth_date": birth_date, "telefone": telefone,
                "error": "O cadastro e permitido somente para maiores de 18 anos.",
            })

        # Verificar email duplicado
        existing = request.env["res.users"].sudo().search([("login", "=", email)], limit=1)
        if existing:
            return request.render("portal_club_support.jj_register_page", {
                "name": name,
                "cpf": cpf,
                "birth_date": birth_date,
                "telefone": telefone,
                "error": "Este e-mail ja esta cadastrado. Tente fazer login.",
            })

        # ---- SELFIE UPLOAD ----
        selfie_data = None
        selfie_filename = None
        if "selfie" in request.httprequest.files:
            f = request.httprequest.files["selfie"]
            if f.filename:
                selfie_data = _b64.b64encode(f.read()).decode("ascii")
                selfie_filename = f.filename

        # Crear partner y usuario
        try:
            with request.env.cr.savepoint():
                partner_vals = {
                    "name": name,
                    "email": email,
                    "l10n_br_cpf": cpf,
                    "birth_date": parsed_birth_date,
                    "phone": telefone,
                    "age_confirmed": True,
                    "terms_accepted_date": fields.Datetime.now(),
                }
                partner = request.env["res.partner"].sudo().create(partner_vals)

                # Guardar selfie como attachment en el partner
                if selfie_data and selfie_filename:
                    request.env["ir.attachment"].sudo().create({
                        "name": selfie_filename,
                        "datas": selfie_data,
                        "res_model": "res.partner",
                        "res_id": partner.id,
                        "type": "binary",
                        "mimetype": f.content_type or "image/jpeg",
                    })

                portal_group = request.env.ref("base.group_portal")
                request.env["res.users"].sudo().with_context(
                    no_reset_password=True
                ).create({
                    "login": email,
                    "password": password,
                    "partner_id": partner.id,
                    "groups_id": [(6, 0, [portal_group.id])],
                })

            request.env.cr.commit()
            _logger.info("JJ-REG: commit OK for %s", email)

            try:
                result = request.session.authenticate(request.db, {
                    "login": email,
                    "password": password,
                    "type": "password",
                })
                _logger.info("JJ-REG: authenticate OK result=%s uid=%s", result, request.session.uid)
            except Exception as e:
                _logger.error("JJ-REG: authenticate FAILED: %s", e, exc_info=True)
                # fallback: lookup user and set session manually
                user = request.env["res.users"].sudo().search([("login", "=", email)], limit=1)
                if user:
                    _logger.info("JJ-REG: fallback user found uid=%s", user.id)
                    request.session.update({
                        "db": request.db,
                        "login": email,
                        "uid": user.id,
                        "session_token": user._compute_session_token(request.session.sid),
                    })
                    request.session.should_rotate = True
                    _logger.info("JJ-REG: fallback session set uid=%s", request.session.uid)

            _logger.info("JJ-REG: redirecting to clubs")
            return request.redirect("/my/club-support/clubs")

        except Exception as e:
            return request.render("portal_club_support.jj_register_page", {
                "name": name,
                "email": email,
                "cpf": cpf,
                "birth_date": birth_date,
                "telefone": telefone,
                "error": f"Erro ao criar conta: {str(e)}",
            })

    # --------------------------------------------------
    # SELECCION DE CLUBES -- Step 2: Seus clubes
    # --------------------------------------------------
    @http.route("/my/club-support/clubs", type="http", auth="user", website=True, sitemap=False)
    def club_support_clubs(self, **kw):
        partner = request.env.user.partner_id
        categories = request.env["club.support.game.category"].sudo().search(
            [("active", "=", True)], order="sequence, id"
        )
        preferences = request.env["club.support.preference"].sudo().search([
            ("partner_id", "=", partner.id),
            ("active", "=", True),
        ])
        prefs_by_category = {p.category_id.id: p for p in preferences}
        federations = request.env["casino.federation"].sudo().search(
            [("active", "=", True)], order="name, id"
        )
        # LOTE 2: popular clubs — top 8 by preference count, tiebreaker by sequence
        pref_counts = request.env["club.support.preference"].sudo().read_group(
            [("active", "=", True), ("casino_club_id", "!=", False)],
            ["casino_club_id"],
            ["casino_club_id"],
        )
        popular_ids = []
        for entry in pref_counts:
            club_id = entry.get("casino_club_id")
            if club_id and isinstance(club_id, (tuple, list)):
                popular_ids.append((club_id[0], entry.get("casino_club_id_count", 0)))
        # sort by count desc, keep top 8
        popular_ids.sort(key=lambda x: x[1], reverse=True)
        popular_ids = [cid for cid, _ in popular_ids[:8]]
        popular_clubs = request.env["casino.club"].sudo().search(
            [("id", "in", popular_ids), ("active", "=", True)],
            order="sequence, name"
        ) if popular_ids else request.env["casino.club"]
        # LOTE 2+1: current user selections across all categories (for TUS CLUBES)
        current_clubs = []
        for pref in preferences:
            if pref.casino_club_id and pref.casino_club_id.active:
                current_clubs.append({
                    "id": pref.casino_club_id.id,
                    "name": pref.casino_club_id.name,
                    "short_name": pref.casino_club_id.short_name,
                    "primary_color": pref.casino_club_id.primary_color or "#073b2a",
                    "logo": pref.casino_club_id.logo,
                    "category_id": pref.category_id.id,
                    "category_name": pref.category_id.name,
                })
        return request.render("portal_club_support.jj_clubs_page", {
            "partner": partner,
            "categories": categories,
            "prefs_by_category": prefs_by_category,
            "federations": federations,
            "popular_clubs": popular_clubs,
            "current_clubs": current_clubs,
        })

    # --------------------------------------------------
    # DASHBOARD -- /my/club-support
    # --------------------------------------------------
    @http.route("/my/club-support", type="http", auth="user", website=True, sitemap=False)
    def club_support_main(self, **kw):
        partner = request.env.user.partner_id
        success = kw.get("success") == "1"
        preferences = request.env["club.support.preference"].sudo().search([
            ("partner_id", "=", partner.id),
            ("active", "=", True),
        ])
        clubs_data = []
        for pref in preferences:
            club = pref.casino_club_id
            category = pref.category_id
            clubs_data.append({
                "category_name": category.name,
                "club_name": club.name,
                "club_short": club.short_name,
                "club_color": club.primary_color or "#0f3d2a",
                "club_logo": club.logo,
                "commission_description": category.commission_description,
                "pref_id": pref.id,
            })
        categories = request.env["club.support.game.category"].sudo().search(
            [("active", "=", True)], order="sequence, name, id"
        )
        featured_games = request.env["product.template"]
        for category in categories:
            featured_games |= category.featured_game_ids.filtered(
                lambda game: game.active and game.is_game and game.website_published
            )
        featured_games = featured_games[:3]
        return request.render("portal_club_support.jj_dashboard_page", {
            "partner": partner,
            "clubs_data": clubs_data,
            "success": success,
            "featured_games": featured_games,
            "featured_game_empty_slots": max(0, 3 - len(featured_games)),
            "success_message": "Cadastro concluido com sucesso!",
        })

    # --------------------------------------------------
    # SAVE -- POST para guardar preferencias
    # --------------------------------------------------
    @http.route("/my/club-support/save", type="http", auth="user", website=True,
                csrf=True, sitemap=False)
    def club_support_save(self, **kw):
        if request.httprequest.method == "GET":
            return request.redirect("/my/club-support/clubs")
        partner = request.env.user.partner_id
        Preference = request.env["club.support.preference"].sudo()
        Category = request.env["club.support.game.category"].sudo()
        Club = request.env["casino.club"].sudo()
        redirect_to = kw.get("redirect_to", "main")
        now = fields.Datetime.now()
        saved = []
        for key, value in kw.items():
            if not key.startswith("club_"):
                continue
            try:
                category_id = int(key.replace("club_", ""))
                club_id = int(value)
            except (ValueError, TypeError):
                continue
            category = Category.browse(category_id)
            if not category.exists() or not category.active:
                continue
            club = Club.browse(club_id)
            if not club.exists() or not club.active:
                continue
            existing = Preference.search([
                ("partner_id", "=", partner.id),
                ("category_id", "=", category_id),
                ("active", "=", True),
            ], limit=1)
            if existing:
                if existing.casino_club_id.id != club_id:
                    existing.write({"casino_club_id": club_id, "changed_date": now})
            else:
                Preference.create({
                    "partner_id": partner.id,
                    "category_id": category_id,
                    "casino_club_id": club_id,
                    "selected_date": now,
                    "changed_date": now,
                })
            saved.append({"category": category.name, "club": club.name, "color": club.primary_color or "#0f3d2a", "club_id": club_id})
        if redirect_to == "done":
            return request.render("portal_club_support.jj_done_page", {
                "partner": partner,
                "selected_clubs": saved,
            })
        return request.redirect("/my/club-support?success=1")
# --------------------------------------------------
    # WHOAMI -- JSON endpoint for session status
    # --------------------------------------------------
    @http.route("/club-support/whoami", type="http", auth="public", website=True,
                csrf=False, sitemap=False)
    def club_support_whoami(self):
        user = request.env.user
        logged = user and user.id != request.env.ref('base.public_user').id
        return request.make_json_response({
            "name": user.partner_id.name if logged else None,
            "user_id": user.id if logged else None,
        })
