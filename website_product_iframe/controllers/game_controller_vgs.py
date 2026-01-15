from datetime import timedelta, datetime
import hashlib
import token

import requests
from odoo import http, fields
from odoo.http import request, route, Response
import logging
import time
import uuid
import json

_logger = logging.getLogger(__name__)
class CasinoError(Exception):
    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def to_dict(self):
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                # "http_status": self.http_status
            }
        }

class CasinoErrorCodes:
    INSUFFICIENT_FUNDS = (1, "Not enough money on player’s wallet", 402)
    AUTHORIZATION_FAILED = (2, "Authorization header is wrong", 401)
    TOKEN_EXPIRED = (3, "Token session is expired", 403)
    UNKNOWN_TRANSACTION_ID = (4, "Transaction ID is unknown", 404)
    INVALID_GAME = (5, "Invalid game", 405)
    INVALID_AMOUNT = (6, "Invalid amount", 406)
    INVALID_TOKEN = (7, "Invalid token", 407)
    TRANSACTION_ALREADY_SETTLED = (8, "Transaction has already been settled", 408)
    DEBIT_TRANSACTION_DOES_NOT_EXIST = (9, "Debit transaction does not exist", 409)
    INVALID_PARAMETER = (400, "Invalid parameter", 400)
    GENERIC_ERROR = (900, "An unexpected error occurred", 900)

def error_response(error: CasinoError):
    return Response(json.dumps(error.to_dict()), content_type='application/json', status=error.http_status)

def _lower_params(args):
    """Devuelve un dict con claves en minúsculas para soportar 'Not Case Sensitive'."""
    return {k.lower(): v for k, v in (args or {}).items()}

def _md5_hex(s: str) -> str:
    _logger.info("Calculating MD5 hex of string: %s ----- hash: %s", s, hashlib.md5(s.encode("utf-8")).hexdigest())
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def _get_conf(key, default=None):
    return request.env["ir.config_parameter"].sudo().get_param(key, default)

def _check_ip_whitelist():
    # Recomendación spec: whitelisting a IPs de VGS
    allowed = _get_conf("vgs.allowed_ips", "")
    if not allowed:
        return True
    allowed_set = {ip.strip() for ip in allowed.split(",") if ip.strip()}
    origin = request.httprequest.remote_addr or ""
    return (origin in allowed_set)

def _xml_envelope(req_params_xml: str, resp_xml: str) -> str:
    return f"""<VGSSYSTEM>
        <REQUEST>
            <PARAMS>{req_params_xml}</PARAMS>
        </REQUEST>
        <TIME>{fields.Datetime.now()}</TIME>
        <RESPONSE>
        {resp_xml}
        </RESPONSE>
        </VGSSYSTEM>"""

def _xml_tag(name, value):
    v = "" if value is None else str(value)
    return f"<{name.upper()}>{(v)}</{name.upper()}>"

def _hash_ok(method, params_lower):
    _logger.info("**** Hash check for method %s with params: %s", method, json.dumps(params_lower, indent=2, ensure_ascii=False))
    passkey = _get_conf("vgs.passkey", "Hola Mundo")
    _logger.info("**** passkey: %s", passkey)
    if not passkey:
        return False
    client_hash = params_lower.get("hash", "") or params_lower.get("Hash", "")
    if not client_hash:
        return False

    if method == "authenticate":
        # MD5(Token+PassKey)  (orden exacto)
        base = f"{params_lower.get('token','')}{passkey}"
    elif method == "changebalance":
        # MD5(userId+amount+trnType+TrnDescription+roundId+gameId+History+PassKey)
        base = (
            f"{params_lower.get('userid','')}"
            f"{params_lower.get('amount','')}"
            f"{params_lower.get('trntype','')}"
            f"{params_lower.get('trndescription','')}"
            f"{params_lower.get('roundid','')}"
            f"{params_lower.get('gameid','')}"
            f"{params_lower.get('history','')}"
            f"{passkey}"
        )
    elif method == "status":
        # MD5(userId+CasinoTransactionID+PassKey)
        base = (
            f"{params_lower.get('userid','')}"
            f"{params_lower.get('casinotransactionid','')}"
            f"{passkey}"
        )
    elif method == "getbalance":
        # MD5(userId+PassKey)
        base = f"{params_lower.get('userid','')}{passkey}"
    else:
        return False

    calc = _md5_hex(base)
    _logger.info("**** Hash check for method %s: base='%s' calc='%s' client='%s'", method, base, calc, client_hash)
    return calc.lower() == client_hash.lower()

class GameControllerVGS(http.Controller):
    def _raise_casino_error(self, code_tuple_or_code, override_msg=None):
        """
        Lanza CasinoError reemplazando el mensaje del tuple si corresponde.
        Soporta tuplas (code, msg) y (code, msg, http_status) o un code suelto.
        """
        ct = code_tuple_or_code
        if isinstance(ct, tuple):
            if len(ct) == 3:
                code, _msg, status = ct
                raise CasinoError(code, override_msg or _msg, status)
            elif len(ct) == 2:
                code, _msg = ct
                raise CasinoError(code, override_msg or _msg)
            else:
                # forma inesperada: pásala tal cual
                raise CasinoError(*ct)
        else:
            # code suelto
            raise CasinoError(ct, override_msg or "Error")
        
    def _update_limits_softcap(self, partner, company, amount):
        """
        Imputa 'amount' a los acumulados de casino.game.bet.limits (diario/semanal/mensual)
        con política soft-cap:
          - Permite si (para todos los períodos con límite > 0) spent <= limit (antes del update).
            Esto deja cruzar el límite en esta jugada.
          - Rechaza si alguno ya estaba spent > limit (antes del update).
        Devuelve dict:
          allowed: bool
          crossed: set de períodos {"daily","weekly","monthly"} que cruzaron/alcan-zaron el límite
          message_map: período->mensaje (desde res.company)
        """
        Bet = request.env['casino.game.bet.limits'].sudo()
        _logger.info(
            'SoftCap: partner=%s company=%s amount=%.6f',
            partner.id, company.id, amount
        )

        # get-or-create, robusto ante concurrencia (unique(partner_id, company_id))
        bl = Bet.search([('partner_id', '=', partner.id), ('company_id', '=', company.id)], limit=1)
        if not bl:
            try:
                with request.env.cr.savepoint():
                    bl = Bet.create({
                        'partner_id': partner.id,
                        'company_id': company.id,
                        'limit_daily': 0.0, 'limit_weekly': 0.0, 'limit_monthly': 0.0,
                        'spent_daily': 0.0, 'spent_weekly': 0.0, 'spent_monthly': 0.0,
                    })
            except IntegrityError:
                request.env.cr.rollback()
                bl = Bet.search([('partner_id', '=', partner.id), ('company_id', '=', company.id)], limit=1)

        # Opcional: ventanas rodantes
        try:
            bl._maybe_roll_windows()
        except Exception:
            pass

        cr = request.env.cr
        _logger.info('SoftCap: UPDATE id=%s amount=%.6f', bl.id, amount)

        # UPDATE atómico: permite cruzar el límite; bloquea si YA estaba excedido (spent > limit)
        cr.execute("""
            UPDATE casino_game_bet_limits bl
               SET spent_daily   = COALESCE(bl.spent_daily,   0) + %(amt)s,
                   spent_weekly  = COALESCE(bl.spent_weekly,  0) + %(amt)s,
                   spent_monthly = COALESCE(bl.spent_monthly, 0) + %(amt)s,
                   last_reset_daily   = COALESCE(bl.last_reset_daily,   NOW()),
                   last_reset_weekly  = COALESCE(bl.last_reset_weekly,  NOW()),
                   last_reset_monthly = COALESCE(bl.last_reset_monthly, NOW())
             WHERE bl.id = %(id)s
               AND (COALESCE(bl.limit_daily,  0) = 0 OR COALESCE(bl.spent_daily,   0) <= COALESCE(bl.limit_daily,  0))
               AND (COALESCE(bl.limit_weekly, 0) = 0 OR COALESCE(bl.spent_weekly,  0) <= COALESCE(bl.limit_weekly, 0))
               AND (COALESCE(bl.limit_monthly,0) = 0 OR COALESCE(bl.spent_monthly, 0) <= COALESCE(bl.limit_monthly,0))
         RETURNING
               COALESCE(bl.spent_daily,   0)             AS new_daily,
               COALESCE(bl.spent_weekly,  0)             AS new_weekly,
               COALESCE(bl.spent_monthly, 0)             AS new_monthly,
               COALESCE(bl.limit_daily,   0)             AS limit_daily,
               COALESCE(bl.limit_weekly,  0)             AS limit_weekly,
               COALESCE(bl.limit_monthly, 0)             AS limit_monthly,
               COALESCE(bl.spent_daily,   0) - %(amt)s   AS prev_daily,
               COALESCE(bl.spent_weekly,  0) - %(amt)s   AS prev_weekly,
               COALESCE(bl.spent_monthly, 0) - %(amt)s   AS prev_monthly
        """, {"id": bl.id, "amt": float(amount or 0.0)})

        if cr.rowcount == 0:
            # Ya estaba excedido antes: identificar período bloqueante (todo coalesceado)
            cr.execute("""
                SELECT
                  COALESCE(spent_daily,   0) AS sd, COALESCE(limit_daily,   0) AS ld,
                  COALESCE(spent_weekly,  0) AS sw, COALESCE(limit_weekly,  0) AS lw,
                  COALESCE(spent_monthly, 0) AS sm, COALESCE(limit_monthly, 0) AS lm
                FROM casino_game_bet_limits
                WHERE id = %s
            """, (bl.id,))
            row = cr.fetchone()
            if not row:
                return {"allowed": True, "crossed": set(), "message_map": {}}

            sd, ld, sw, lw, sm, lm = row

            def exceeded(spent, limit):
                return (limit > 0) and (spent > limit)

            if exceeded(sd, ld):
                msg = bl.company_id.bet_msg_daily or "Has alcanzado tu límite diario."
                return self._raise_casino_error(
                    getattr(CasinoErrorCodes, "LIMIT_DAILY_EXCEEDED", CasinoErrorCodes.INSUFFICIENT_FUNDS),
                    override_msg=msg
                )
            if exceeded(sw, lw):
                msg = bl.company_id.bet_msg_weekly or "Has alcanzado tu límite semanal."
                return self._raise_casino_error(
                    getattr(CasinoErrorCodes, "LIMIT_WEEKLY_EXCEEDED", CasinoErrorCodes.INSUFFICIENT_FUNDS),
                    override_msg=msg
                )
            if exceeded(sm, lm):
                msg = bl.company_id.bet_msg_monthly or "Has alcanzado tu límite mensual."
                return self._raise_casino_error(
                    getattr(CasinoErrorCodes, "LIMIT_MONTHLY_EXCEEDED", CasinoErrorCodes.INSUFFICIENT_FUNDS),
                    override_msg=msg
                )

            # sin límites > 0 -> permitir
            return {"allowed": True, "crossed": set(), "message_map": {}}

        # UPDATE aceptado: leer exactamente una vez
        row = cr.fetchone()
        if not row:
            _logger.warning("SoftCap: RETURNING vacío para id=%s (amt=%.6f)", bl.id, amount)
            return {"allowed": True, "crossed": set(), "message_map": {}}

        new_d, new_w, new_m, ld, lw, lm, prev_d, prev_w, prev_m = row
        _logger.info('SoftCap: RETURNING id=%s -> %s', bl.id, row)

        crossed = set()
        if ld > 0 and prev_d <= ld and new_d >= ld:
            crossed.add("daily")
        if lw > 0 and prev_w <= lw and new_w >= lw:
            crossed.add("weekly")
        if lm > 0 and prev_m <= lm and new_m >= lm:
            crossed.add("monthly")

        message_map = {
            "daily":   bl.company_id.bet_msg_daily   or "Has alcanzado tu límite diario.",
            "weekly":  bl.company_id.bet_msg_weekly  or "Has alcanzado tu límite semanal.",
            "monthly": bl.company_id.bet_msg_monthly or "Has alcanzado tu límite mensual.",
        }
        return {"allowed": True, "crossed": crossed, "message_map": message_map}
    
    def _prepare_session_vals(self, game_id, round_id, user_id, token, initial_balance, final_balance, amount, state, result, transaction_id, internal_transaction_id, json_data):
        """
        Devuelve los valores para crear una sesión de juego.
        """
        product_name = ""
        # if not product_id is None and product_id != 0:
        product = request.env['product.product'].sudo().search([('id', '=', game_id)], limit=1)
        #     product_name = product.name

        partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
        user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        user_id = user.id
        to_win = 0.0
        if not json_data.get('endRound'):
            to_win_val = json_data.get('to_win')
            if to_win_val is not None:
                to_win = float(to_win_val)

        _logger.info(f"Casino Iframe: Starting game session for product: {product.id} - {product.name}")
        return {
            'game_id': product.id,
            'round_id': round_id,
            'user_id': user_id,
            'token': token,
            'transaction_id': transaction_id,
            'internal_transaction_id': internal_transaction_id,
            'start_datetime': fields.Datetime.now(),
            'end_datetime': fields.Datetime.now() + timedelta(hours=1),
            'result': result,
            'state': state,
            'amount': amount,
            'to_win': to_win,
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'currency_id': request.env.company.currency_id.id,
            'description': f'Inicio de juego: {product_name}',
            'json_data': json_data
        }

    def _prepare_move_vals(self, token, product, account, debit, credit, op):
        """
        Devuelve los valores para crear un asiento contable balanceado en account.move con dos líneas (account.move.line).
        """
        partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
        cuenta_ingreso = account
        cuenta_contrapartida = request.env['account.account'].sudo().search([
            ('code', '=', '110101')  # Ajusta el código según tu plan contable (ejemplo: caja/banco)
        ], limit=1)
        if not cuenta_contrapartida:
            cuenta_contrapartida = request.env['account.account'].sudo().create({
                'name': 'Contrapartida Casino',
                'code': '110101',
                'account_type': 'asset_receivable',
            })

        return {
            'name': f'Juego: {product}',
            'journal_id': request.env['account.journal'].sudo().search([
                ('type', '=', 'general')], limit=1
            ).id,
            'date': fields.Datetime.today(),
            'ref': f'Casino Game - {product}',
            'line_ids': [
                (0, 0, {
                    'name': f'Ingreso juego: {product}',
                    'account_id': cuenta_ingreso.id,
                    'partner_id': partner.id,
                    'debit': debit,
                    'credit': credit,
                }),
                (0, 0, {
                    'name': 'WIN' if op == 'win' else 'LOSE' if op == 'lose' else 'DEPOSIT' if op == 'deposit' else 'WITHDRAW',
                    'account_id': cuenta_contrapartida.id,
                    'partner_id': partner.id,
                    'debit': credit,
                    'credit': debit,
                }),
            ]
        }

    def _get_balance_user(self, token):
        try:
            user = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            return user.balance_game
        except Exception as e:
            _logger.error('Casino Iframe: Error en _get_balance_user: %s', str(e))
            return 0.0
    

    # ==================== API principal (VGS spec) =====================
    @http.route(['/api/vgs/v1/authenticate.do'], type='http', auth='public', methods=['GET'], csrf=False)
    def authenticate(self, **kwargs):
        params = _lower_params(kwargs)
        _logger.info("**** 1 - Casino Iframe: authenticate called with params: %s", json.dumps(params, indent=2, ensure_ascii=False))
        if not _check_ip_whitelist():
            # 399 Internal Error / permiso denegado; aquí devolvemos FAILED genérico
            req_xml = _xml_tag("TOKEN", params.get("token")) + _xml_tag("HASH", params.get("hash"))
            _logger.warning("**** 2 - Casino Iframe: authenticate - IP no permitida: %s", request.httprequest.remote_addr)
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "399"))

        # Hash
        if not _hash_ok("authenticate", params):
            req_xml = _xml_tag("TOKEN", params.get("token")) + _xml_tag("HASH", params.get("hash"))
            _logger.error("**** 3 - Casino Iframe: authenticate - req_xml: %s", json.dumps(req_xml, indent=2, ensure_ascii=False))
            _logger.warning("**** 4 - Casino Iframe: authenticate - Hash inválido para params: %s", json.dumps(params, indent=2, ensure_ascii=False))
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "500"))  # Invalid hash

        token = params.get("token", "")
        #session = request.env["vgs.session"].sudo().search([("name", "=", token), ("active", "=", True)], limit=1)
        user = request.env['res.partner'].sudo().search(['|', ('token', '=', token), ('secret_token', '=', token)], limit=1)

        req_xml = _xml_tag("TOKEN", token) + _xml_tag("HASH", params.get("hash"))
        _logger.info("**** 5 - Casino Iframe: authenticate - req_xml: %s", json.dumps(req_xml, indent=2, ensure_ascii=False))
        if not user:
            # Invalid token
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "400"))  # Invalid token

        balance = self._get_balance_user(token)
        resp = (
            _xml_tag("RESULT", "OK")
            + _xml_tag("USERID", user.ref or str(user.id))
            + _xml_tag("USERNAME", user.nickname or user.name or "")
            + _xml_tag("FIRSTNAME", user.name or "")
            + _xml_tag("LASTNAME", "")
            + _xml_tag("EMAIL", user.email or "")
            + _xml_tag("CURRENCY", user.currency_id.name)
            + _xml_tag("BALANCE", f"{balance:.2f}")
            + _xml_tag("GAMESESSIONID", "") #session.id if session else "") user.gamesessionid
        )
        return _xml_envelope(req_xml, resp)
    
    # -----------------------
    # /ChangeBalance.aspx
    # -----------------------
    @http.route(['/api/vgs/v1/ChangeBalance.aspx'], type='http', auth='public', methods=['GET'], csrf=False)
    def change_balance(self, **kwargs):
        _logger.info(">>>> ChangeBalance: Casino Iframe: change_balance called with params: %s", json.dumps(kwargs, indent=2, ensure_ascii=False))
        params = _lower_params(kwargs)
        _logger.info(">>>> ChangeBalance: _lower_params: %s", json.dumps(params, indent=2, ensure_ascii=False))
        
        if not _check_ip_whitelist():
            req_xml = "".join([
                _xml_tag("USERID", params.get("userid")),
                _xml_tag("AMOUNT", params.get("amount")),
                _xml_tag("TRANSACTIONID", params.get("transactionid")),
                _xml_tag("TRNTYPE", params.get("trntype")),
                _xml_tag("GAMEID", params.get("gameid")),
                _xml_tag("ROUNDID", params.get("roundid")),
                _xml_tag("TRNDESCRIPTION", params.get("trndescription")),
                _xml_tag("HISTORY", params.get("history")),
                _xml_tag("ISROUNDFINISHED", params.get("isroundfinished")),
                _xml_tag("DEALERID", params.get("dealerid")),
                _xml_tag("HASH", params.get("hash")),
            ])
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "399"))

        if not _hash_ok("changebalance", params):
            req_xml = _xml_tag("USERID", params.get("userid")) + _xml_tag("HASH", params.get("hash"))
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "500"))

        user_ref = params.get("userid", "")
        amount_s = params.get("amount", "0")
        trntype = params.get("trntype", "").upper()
        round_id = params.get("roundid", "")
        game_id = params.get("gameid", "")
        trndesc = params.get("trndescription", "")
        history = params.get("history", "")
        dealer_id = params.get("dealerid", "")
        casino_tx = params.get("transactionid", "")

        req_xml = "".join([
            _xml_tag("USERID", user_ref),
            _xml_tag("AMOUNT", amount_s),
            _xml_tag("TRANSACTIONID", casino_tx),
            _xml_tag("TRNTYPE", trntype),
            _xml_tag("GAMEID", game_id),
            _xml_tag("ROUNDID", round_id),
            _xml_tag("TRNDESCRIPTION", trndesc),
            _xml_tag("HISTORY", history),
            _xml_tag("ISROUNDFINISHED", params.get("isroundfinished")),
            _xml_tag("DEALERID", dealer_id),
            _xml_tag("HASH", params.get("hash")),
        ])

        product_id = request.env['product.product'].sudo().search([('game_id', '=', game_id)], limit=1).id
        partner = request.env['res.partner'].sudo().search([('id', '=', user_ref)], limit=1)
        _logger.info(">>>> ChangeBalance: Found partner: %s", partner)

        if not partner:
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "310"))  # Unknown userId

        # Moneda desde la wallet existente del partner; si necesitas multicurrency avanzada, amplía aquí
        # (Authenticate ya fija la currency del jugador en VGS según primera activación)
        # Para EC usamos la que tenga su wallet local.
        # user = request.env['res.users'].sudo().browse(int(user_ref))
        user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if user is not None:
            token = user.partner_id.token

        session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
        _logger.info(">>>> ChangeBalance: Found session: %s", session)


        balance = self._get_balance_user(token)
        _logger.info(">>>> ChangeBalance: User balance: %s", balance)
        _logger.info(">>>> ChangeBalance: Current balance: %s", balance)
        
        try:
            amount = float(amount_s or "0")
        except Exception:
            amount = 0.0
        
        amount = amount #Viene con decimales
        # Política de saldo:
        # - BET: debita; si no hay fondos suficientes -> FAILED + code 300 y NO tocar balance
        # - WIN / CANCELLED_BET: acredita (puede venir 0 en WIN para correlación) -> OK
        # - TIP: debita como BET (si quieres separar, extiende)
        internal_transaction_id = token
        new_balance = balance
        if trntype == "BET" or trntype == "TIP":
            if amount > balance:
                return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "300"))

            result = self._apply_amount(session.id, product_id, round_id = round_id, amount=amount, to_win=0.0, op="lose" if trntype == "BET" else "tip", token=token, transaction_id=casino_tx, internal_transaction_id=internal_transaction_id)
        elif trntype in ("WIN", "CANCELLED_BET"):
            result = self._apply_amount(session.id, product_id, round_id = round_id, amount=amount, to_win=0.0, op='win', token=token, transaction_id=casino_tx, internal_transaction_id=internal_transaction_id)
        else:
            # Tipo desconocido: failed genérico 301
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "301"))

        new_balance = result.get("balance", balance)
        resp = (
            _xml_tag("RESULT", "OK")
            + _xml_tag("ECSYSTEMTRANSACTIONID", internal_transaction_id)
            + _xml_tag("BALANCE", f"{new_balance:.2f}")
        )
        return _xml_envelope(req_xml, resp)
    
    # -----------------------
    # /requeststatus.do
    # -----------------------
    @http.route(['/api/vgs/v1/requeststatus.do'], type='http', auth='public', methods=['GET'], csrf=False)
    def request_status(self, **kwargs):
        params = _lower_params(kwargs)
        if not _check_ip_whitelist():
            req_xml = _xml_tag("USERID", params.get("userid")) + _xml_tag("CASINOTRANSACTIONID", params.get("casinotransactionid")) + _xml_tag("HASH", params.get("hash"))
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "399"))

        if not _hash_ok("status", params):
            req_xml = _xml_tag("USERID", params.get("userid")) + _xml_tag("CASINOTRANSACTIONID", params.get("casinotransactionid")) + _xml_tag("HASH", params.get("hash"))
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "500"))

        user_ref = params.get("userid", "")
        casino_tx = params.get("casinotransactionid", "")

        req_xml = _xml_tag("USERID", user_ref) + _xml_tag("CASINOTRANSACTIONID", casino_tx) + _xml_tag("HASH", params.get("hash"))
        # Tx = request.env["vgs.transaction"].sudo()
        # tx = Tx.search([("user_ref", "=", user_ref), ("casino_transaction_id", "=", casino_tx)], limit=1)

        partner = request.env['res.partner'].sudo().search([('id', '=', user_ref)], limit=1)
        _logger.info(">>>> RequestStatus: Found partner: %s", partner)
        if not partner:
            # 302: unknown transaction id (GetStatus) según spec
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "302"))
        
        # user = request.env['res.users'].sudo().browse(int(user_ref))
        user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        _logger.info(">>>> RequestStatus: Found user: %s", user)
        if user is not None:
            token = user.partner_id.token

        
        session = request.env['casino.game.session'].sudo()
        all_sessions = session.search([])
        # _logger.info(">>>> RequestStatus: session model count: %s", len(all_sessions))
        # for sess in all_sessions:
        #     _logger.info(">>>> RequestStatus: session fields: %s", sess.read()[0] if sess.exists() else "No data")
        # _logger.info(">>>> RequestStatus: session model structure: %s", session._fields.keys() if hasattr(session, '_fields') else "No fields info")

        session = session.search([('token', '=', token), ("transaction_id", "=", casino_tx)], limit=1) if all_sessions else None
        _logger.info(">>>> RequestStatus: Found session: %s - Token: %s - transaction_id: %s", session, token, casino_tx)

        if not session:
            # 302: unknown transaction id (GetStatus) según spec
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "302"))

        return _xml_envelope(req_xml, _xml_tag("RESULT", "OK") + _xml_tag("ECSYSTEMTRANSACTIONID", session.transaction_id))

    # -----------------------
    # /getbalance.do
    # -----------------------
    @http.route(['/api/vgs/v1/getbalance.do'], type='http', auth='public', methods=['GET'], csrf=False)
    def get_balance(self, **kwargs):
        params = _lower_params(kwargs)
        if not _check_ip_whitelist():
            req_xml = _xml_tag("USERID", params.get("userid")) + _xml_tag("HASH", params.get("hash"))
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "399"))

        if not _hash_ok("getbalance", params):
            req_xml = _xml_tag("USERID", params.get("userid")) + _xml_tag("HASH", params.get("hash"))
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "500"))

        user_ref = params.get("userid", "")
        req_xml = _xml_tag("USERID", user_ref) + _xml_tag("HASH", params.get("hash"))

        partner = request.env['res.partner'].sudo().search([('id', '=', user_ref)], limit=1)
        if not partner:
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "310"))

        # user = request.env['res.users'].sudo().browse(int(user_ref))
        user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not user:
            return _xml_envelope(req_xml, _xml_tag("RESULT", "FAILED") + _xml_tag("CODE", "310"))

        if user is not None:
            token = user.partner_id.token

        balance = self._get_balance_user(token)
        if not balance:
            # Sin wallet aún => 0.00
            balance_str = "0.00"
        else:
            balance_str = f"{balance:.2f}"

        return _xml_envelope(req_xml, _xml_tag("RESULT", "OK") + _xml_tag("BALANCE", balance_str))
    
    # ==================== FIN API principal (VGS spec) =====================



    @http.route('/api/vgs/v1/start_game', type='json', auth='public', methods=['POST'], csrf=False)
    def start_game(self, product_id, transaction_id, token, **kwargs):
        """
        Registra el inicio de una sesión de juego y movimiento contable
        """
        try:
            # Obtener datos del request
            user = request.env.user
            
            # Buscar el producto
            product_id = None
            if not product_id is None and product_id != 0:
                product_id = int(product_id)
                product = request.env['product.template'].sudo().browse(product_id)
                if not product.exists():
                    return {'error': 'Producto no encontrado'}
            
            return {
                'success': True,
                'message': 'Sesión iniciada correctamente'
            }
            
        except Exception as e:
            return {
                'error': f'Error al iniciar sesión: {str(e)}'
            }
        
    @http.route('/api/vgs/v1/end_game', type='json', auth='public', methods=['POST'], csrf=False)
    def end_game(self, session_id, amount, **kwargs):
        """
        Finaliza una sesión de juego
        """
        data = request.get_json_data()
        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')

        roundId = data.get('roundId', None)
        if roundId is None:
            roundId = data.get('params', {}).get('roundId')

        gameId = data.get('gameId', None)
        if gameId is None:
            gameId = data.get('params', {}).get('gameId')

        endGame = data.get('endGame', None)
        if endGame is None:
            endGame = data.get('params', {}).get('endGame')

        roundId = data.get('roundId', None)
        if roundId is None:
            roundId = data.get('params', {}).get('roundId')

        transactionId = data.get('transactionId', None)
        if transactionId is None:
            transactionId = data.get('params', {}).get('transactionId')
        
        amount = data.get('amount', 0.0)
        if amount is None:
            amount = data.get('params', {}).get('amount', 0.0)

        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')

        if token is None:
            token = data.get('data', {}).get('token')

        internal_transaction_id = token #uuid.uuid4().hex
        session = request.env['casino.game.session'].sudo().search([('secret_token', '=', token)], limit=1)
        result = self._apply_amount(session.id, product_id = gameId, round_id = roundId, amount=amount, to_win=0.0, op='win', token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)
        
        # s = request.env['casino.game.session'].sudo().browse(int(session_id))
        
        response = result.get("json_data")
        # {
        #     "balance": result.get("balance", 0.0),
        #     "timestamp": int(time.time() * 1000),
        #     "message": "Fin de juego"
        # }
        return response

    # ===================== API extra (botones) =====================

    @http.route('/api/vgs/v1/login', type='http', auth='public', methods=['POST'], csrf=False)
    def api_login(self, **kwargs):
        """
        Login del juego: alias de start_game. Devuelve también balance actual.
        """
        data = request.get_json_data()
        token = data.get('token', None)
        _logger.info('Casino Iframe: token: %s', token)
        if token is None:
            token = data.get('params', {}).get('token')
        try:
            user = request.env['res.partner'].sudo().search(['|', ('token', '=', token), ('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            _logger.info('Casino Iframe:\napi_login called with kwargs: %s \n----- %s \n----- token: %s \n------ userId: %s \n------', json.dumps(kwargs, indent=2, ensure_ascii=False), data, token, user.id)
            product_id = 0
            transaction_id = 0
            
            result = self.start_game(product_id, transaction_id, token)
            if result.get('error'):
                return result
            session = '' # request.env['casino.game.session'].sudo().browse(result['session_id'])
            
            balance = self._get_balance_user(token)
            _logger.info('Casino Iframe: Balance obtenido: %s', balance)

            if not user.secret_token:
                generated_token = uuid.uuid4().hex
                user.sudo().write({'secret_token': generated_token})
                new_token = generated_token
            else:
                new_token = user.secret_token
            
            response = {
                "token": new_token,
                "balance": int(balance * 100),
                "currency": transaction_id,
                "nickname": user.nickname or user.name,
                "timestamp": int(time.time() * 1000),
                "country": user.country_id.name if user.country_id else "AR",
            }
            return Response(json.dumps(response), content_type='application/json')
            # return response
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            return {'error': f'Error en login: {str(e)}'}

    @http.route('/api/vgs/v1/credit', type='http', auth='public', methods=['POST'], csrf=False)
    def api_win(self, **kwargs):
        """Jugada ganada: suma amount al balance."""
        try:
            data = request.get_json_data()
            token = data.get('token', None)
            if token is None:
                token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            user = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            gameId = data.get('gameId', None)
            if gameId is None:
                gameId = data.get('params', {}).get('gameId')
            if not gameId:
                raise CasinoError(*CasinoErrorCodes.INVALID_GAME)

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')

            endGame = data.get('endGame', None)
            if endGame is None:
                endGame = data.get('params', {}).get('endGame')

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')

            transactionId = data.get('transactionId', None)
            if transactionId is None:
                transactionId = data.get('params', {}).get('transactionId')

            amount = data.get('amount', 0.0)
            if amount is None:
                amount = data.get('params', {}).get('amount', 0.0)
            if not isinstance(amount, (int, float)) or amount <= 0:
                raise CasinoError(*CasinoErrorCodes.INVALID_AMOUNT)

            internal_transaction_id = uuid.uuid4().hex

            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            # if not session:
            #     raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            # Validar fondos insuficientes
            current_balance = self._get_balance_user(token)

            _logger.info('Casino Iframe: api_win called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
            _logger.info('Casino Iframe: Actualizando balance del jugador: %s', json.dumps(kwargs, indent=2, ensure_ascii=False))
            amount = amount / 100
            result = self._apply_amount(session.id, product_id = gameId, round_id = roundId, amount=amount, to_win=0.0, op='win', token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)

            response = {
                "balance": int(result.get("balance", 0.0) * 100),
                "transactionId": internal_transaction_id,
                "timestamp": int(time.time() * 1000)
            }
            return Response(json.dumps(response), content_type='application/json')
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            _logger.error('Casino Iframe: Error inesperado en api credit: %s', str(e))
            ce = CasinoError(*CasinoErrorCodes.GENERIC_ERROR)
            return error_response(ce)
        
    @http.route('/api/vgs/v1/debit', type='http', auth='public', methods=['POST'], csrf=False)
    def api_lose(self, **kwargs):
        """Jugada perdida: resta amount del balance."""
        try:
            data = request.get_json_data()
            token = data.get('token', None)
            if token is None:
                token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            user = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            gameId = data.get('gameId', None)
            if gameId is None:
                gameId = data.get('params', {}).get('gameId')
            if not gameId:
                raise CasinoError(*CasinoErrorCodes.INVALID_GAME)

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')

            endGame = data.get('endGame', None)
            if endGame is None:
                endGame = data.get('params', {}).get('endGame')

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')

            transactionId = data.get('transactionId', None)
            if transactionId is None:
                transactionId = data.get('params', {}).get('transactionId')

            amount = data.get('amount', 0.0)
            if amount is None:
                amount = data.get('params', {}).get('amount', 0.0)
            if not isinstance(amount, (int, float)) or amount <= 0:
                raise CasinoError(*CasinoErrorCodes.INVALID_AMOUNT)

            to_win = data.get('to_win')
            if to_win is None:
                to_win = data.get('params', {}).get('to_win', 0.0)
            if not isinstance(to_win, (int, float)) or to_win < 0:
                to_win = 0.0

            current_balance = self._get_balance_user(token)
            if amount / 100 > current_balance:
                raise CasinoError(*CasinoErrorCodes.INSUFFICIENT_FUNDS)

            internal_transaction_id = uuid.uuid4().hex

            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            # if not session:
            #     raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            # Validar fondos insuficientes (no aplica para débito, pero puedes agregar otras validaciones aquí)

            _logger.info('Casino Iframe: api_lose called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
            amount = amount / 100

            limit_result = self._update_limits_softcap(user, request.env.company, amount)
            #_logger.info('Casino Iframe: Resultado de límites: %s', limit_result)

            result = self._apply_amount(
                session.id,
                product_id=gameId,
                round_id=roundId,
                amount=amount,
                to_wi=to_win,
                op='lose',
                token=token,
                transaction_id=transactionId,
                internal_transaction_id=internal_transaction_id
            )
            _logger.info('Casino Iframe: Resultado de la aplicación de monto: %s', result)
            limit_messages = []
            
            _logger.info('Casino Iframe: Mensajes de límite: %s', limit_messages)
            response = {
                "balance": int(result.get("balance", 0.0) * 100),
                "transactionId": internal_transaction_id,
                "timestamp": int(time.time() * 1000)
            }

            if limit_messages:
                response["limit_messages"] = limit_messages

            return Response(json.dumps(response), content_type='application/json')
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            _logger.error('Casino Iframe: Error inesperado en api debit: %s', str(e))
            ce = CasinoError(*CasinoErrorCodes.GENERIC_ERROR)
            return error_response(ce)
    
    @http.route('/api/vgs/v1/refund', type='json', auth='public', methods=['POST'], csrf=False)
    def api_refund(self, session_id, amount, **kwargs):
        """Devolución de plata: suma amount al balance (crédito)."""
        return self._apply_amount(session_id, product_id = 0, round_id=None, amount = amount, to_win=0.0, op='refund', token="", transaction_id=None)

    @http.route('/api/vgs/v1/balance', type='http', auth='public', methods=['POST'], csrf=False)
    def api_balance(self, **kwargs):
        """Balance: devuelve saldo actual del jugador."""
        try:
            data = request.get_json_data()
            token = data.get('token', None)
            if token is None:
                    token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            _logger.info('Casino Iframe: api_balance called with token: %s', token)
            user = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            _logger.info('Casino Iframe: api_balance called with token: %s', token)

            current_balance = self._get_balance_user(token)
            response = {
                "balance": int(current_balance * 100),
                "timestamp": int(time.time() * 1000) # now
            }
            return Response(json.dumps(response), content_type='application/json')
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            return {'error': f'Error al obtener balance: {str(e)}'}
        
    @http.route('/api/vgs/v1/end', type='json', auth='public', methods=['POST'], csrf=False)
    def api_end(self, session_id, **kwargs):
        """Terminación: alias de end_game."""
        return self.end_game(session_id)


    # ----------------- Helper interno -----------------
    def _apply_amount(self, session_id, product_id, round_id, amount, to_win, op, token, transaction_id, internal_transaction_id):
        """
        Ajusta el balance de la sesión y deja nota en description.
        op: 'win' | 'lose' | 'refund'
        """
        _logger.info('Casino Iframe: Aplicando monto: %s, operación: %s', amount, op)
        try:
            #s = request.env['casino.game.session'].sudo().browse(int(session_id))
            # if not s.exists():
            #     return {'error': 'Sesión no encontrada'}

            amt = float(amount or 0.0)
            if amt < 0:
                _logger.error('Casino Iframe: Monto negativo inválido: %s', amt)
                return {'error': 'Monto inválido'}

            last_session = request.env['casino.game.session'].sudo().search(
                [('token', '=', token)],
                order='id desc',
                limit=1
            )

            _logger.info("Casino Iframe: Token: %s", token)
            partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
            _logger.info('Casino Iframe: Partner encontrado: %s - %s', partner.id, partner.name)
            user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            _logger.info('Casino Iframe: Usuario encontrado: %s', user)
            user_id = user.id
            
            current_balance = self._get_balance_user(token)
            _logger.info('Casino Iframe: Balance actual del usuario: %s', current_balance)

            result = ''
            state = None
            credit = 0.0
            debit = 0.0
            
            json_data = {}
            
            if op == 'win':
                _logger.info('Casino Iframe: WIN')

                new_balance = current_balance + amt
                user.balance_game = new_balance
                note = f'Jugada GANADA +{amt}'
                result = 'win'
                state = 'finished'
                credit = amt
                json_data = {
                    "token": token,
                    "gameId": product_id,
                    "endRound": False,
                    "roundId": "roundId",
                    "transactionId": transaction_id,
                    "amount": amt,
                    "token_live": True,
                }
            elif op == 'lose':
                _logger.info('Casino Iframe: LOSE')
                new_balance = current_balance - amt
                user.balance_game = new_balance
                note = f'Jugada PERDIDA -{amt}'
                result = 'loss'
                state = 'finished'
                debit = amt
                json_data = {
                    "token": token,
                    "gameId": product_id,
                    "endRound": False,
                    "roundId": "roundId",
                    "transactionId": transaction_id,
                    "amount": amt,
                    "token_live": True,
                }
            elif op == 'refund':
                _logger.info('Casino Iframe: REFUND')
                new_balance = current_balance + amt
                user.balance_game = new_balance
                note = f'Devolución +{amt}'
                result = 'abandoned'
                state = 'finished'
                debit = amt
            elif op == 'balance':
                _logger.info('Casino Iframe: BALANCE')
                new_balance = current_balance
                note = f'Estado de Balance: {new_balance}'
                result = 'balance'
                state = 'finished'
                json_data = {
                    "token": token
                }
            elif op == 'finished':
                _logger.info('Casino Iframe: FINISHED')
                new_balance = current_balance + amt
                note = f'Juego terminado. Balance final: {new_balance}'
                result = 'win'
                state = 'finished'
                credit = amt
                json_data = {
                    "balance": new_balance,
                    "timestamp": int(time.time() * 1000),
                    "message": "Fin de juego"
                }
            else:
                _logger.error('Casino Iframe: Operación inválida: %s', op)
                return {'error': 'Operación inválida'}

            _logger.info('Casino Iframe: Creando session')
            _logger.info('Valores para session_vals: product_id=%s, user_id=%s, token=%s, current=%s, new_balance=%s, amt=%s, state=%s, result=%s, transaction_id=%s, json_data=%s',
                product_id, user_id, token, current_balance, new_balance, amt, state, result, transaction_id, json_data)
            try:
                session_vals = self._prepare_session_vals(product_id, round_id, user_id, token, current_balance, new_balance, amt, to_win, state, result, transaction_id, internal_transaction_id, json_data)
                # Si es un débito (apuesta perdida), calcular y guardar comisión del agente
                if op == 'lose':
                    # 1) Determinar agente del jugador (si el módulo de agentes está instalado)
                    agent = None
                    try:
                        if hasattr(partner, '_fields') and 'agent_id' in partner._fields:
                            agent = partner.agent_id
                    except Exception:
                        agent = None

                    # 2) Determinar % de comisión del juego
                    commission_pct = 0.0
                    try:
                        Product = request.env['product.product'].sudo()
                        prod = Product.search(['|', ('id', '=', product_id), ('game_id', '=', str(product_id))], limit=1)
                        if prod:
                            # El campo commission está en product.template, pero es accesible desde product.product
                            commission_pct = float(prod.commission or 0.0)
                    except Exception:
                        commission_pct = 0.0

                    # 3) Calcular importe de comisión
                    try:
                        currency = request.env.company.currency_id
                        commission_amt = (currency.round(amt * commission_pct / 100.0)
                                          if currency else round(amt * commission_pct / 100.0, 2))
                    except Exception:
                        commission_amt = round(amt * commission_pct / 100.0, 2)

                    # 4) Inyectar en la sesión
                    session_vals.update({
                        'agent_id': agent.id if agent else False,
                        'agent_commission': commission_amt,
                    })
            except Exception as e:
                _logger.error('Error en _prepare_session_vals: %s', str(e))
                raise
            _logger.info('Casino Iframe: Session creada %s', session_vals)

            session = request.env['casino.game.session'].sudo().create(session_vals)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session.read())
            
            account = request.env['account.account'].sudo().search([
                ('code', '=', '400001')  # Ajusta según tu plan contable
            ], limit=1)
            
            if not account:
                # Crear cuenta si no existe
                account = request.env['account.account'].sudo().create({
                    'name': 'Cuenta Juegos Casino',
                    'code': '400001',
                    'account_type': 'income',
                })

            _logger.info('Casino Iframe: Cuenta contable encontrada o creada: %s', account)
            move_vals = self._prepare_move_vals(token, product_id, account, debit, credit, op)
            try:
                move = request.env['account.move'].sudo().create(move_vals)
                _logger.info('Asiento contable creado correctamente: %s', move)
            except Exception as e:
                _logger.error('Error al crear el asiento contable: %s', str(e))
                raise
            
            return {'success': True, 'balance': new_balance, 'transaction_id': transaction_id, 'session_id': session.id, 'state': state, 'result': result, 'json_data': json_data}
        except Exception as e:
            _logger.error('Casino Iframe: Error al aplicar monto: %s', str(e))
            return {'error': f'Error al aplicar monto: {str(e)}'}

    @http.route('/api/vgs/v1/get_token', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def get_token(self, user_id=None, **kwargs):
        """Obtención de token."""
        if not user_id:
            return {"error": "user_id requerido"}

        user = request.env['res.users'].sudo().browse(int(user_id))
        if not user.exists():
            return {"error": f"Usuario {user_id} no encontrado"}
        
        _logger.info('Casino Iframe: get_token called with user_id: %s', user_id)
        _logger.info('Tipo de user_id: %s, valor: %r', type(user_id), user_id)
        if user_id is not None:
            user_id = int(user_id)

        user = request.env['res.users'].sudo().browse(user_id)
        
        if user.exists():
            user_data = user.read()[0]
        else:
            _logger.info('Casino Iframe: get_token - Usuario no encontrado para user_id %s', user_id)
        partner = user.partner_id
        _logger.info('Casino Iframe: get_token called with user_id: %s, partner: %s', user_id, partner)
        token = partner.token
        response = {
            "token": token,
        }
        _logger.info('Casino Iframe: get_token called with user_id: %s, token: %s', user_id, token)
        return {"token": token}
        