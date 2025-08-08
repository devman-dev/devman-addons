from odoo import http
from odoo.http import request
from datetime import datetime

from odoo.exceptions import UserError, ValidationError



class MiPortalController(http.Controller):

    @http.route('/my/movimientos2', type='http', auth='user', website=True)
    def portal_movimientos2(self, **kwargs):
        # Datos de prueba simulando movimientos
        movements = [
            {
                'date': datetime(2025, 8, 5),
                'description': 'Depósito inicial',
                'type_display': 'Dep./Retiros',
                'amount': 1000.00,
                'state': 'Completado',
                'balance': 1000.00,
            },
            {
                'date': datetime(2025, 8, 6),
                'description': 'Retiro cajero',
                'type_display': 'Dep./Retiros',
                'amount': -200.00,
                'state': 'Pendiente',
                'balance': 800.00,
            },
            {
                'date': datetime(2025, 8, 7),
                'description': 'Bonus por promoción',
                'type_display': 'Saldo de Bonus',
                'amount': 50.00,
                'state': 'Completado',
                'balance': 850.00,
            },
            {
                'date': datetime(2025, 8, 8),
                'description': 'Transacción juego A',
                'type_display': 'Transacciones de Juegos',
                'amount': -30.00,
                'state': 'Completado',
                'balance': 820.00,
            },
            {
                'date': datetime(2025, 8, 9),
                'description': 'Ajuste manual',
                'type_display': 'Ajustes',
                'amount': 10.00,
                'state': 'Completado',
                'balance': 830.00,
            },
        ]

        return request.render('casino_online.portal_movimientos', {
            'movements': movements,
            'request': request,  # para que funcione request.params en el template
        })
        
        
    
    @http.route('/my/movimientos', type='http', auth='user', website=True)
    def portal_movements(self, **kwargs):
        partner_id = request.env.user.partner_id.id
        company_id = request.env.company.id

        domain = [
            ('company_id', '=', company_id),
            ('partner_id', '=', partner_id),
            ('state', 'in', ['draft', 'posted'])
        ]

        fields_to_read = [
            'date', 'name', 'ref', 'narration',
            'amount_total_signed', 'state', 'move_type',
            'journal_id'
        ]

        moves = request.env['account.move'].sudo().search(domain, order='date asc, id asc')
        data = moves.read(fields_to_read)
        
        
        #raise UserError(f'No se encontraron movimientos contables para el usuario.{data}') 

        def classify(move_dict):
            move_type = move_dict.get('move_type') or ''
            journal = move_dict.get('journal_id')
            journal_name = (journal and isinstance(journal, list) and journal[1]) or ''

            if move_type == 'entry':
                return 'Ajustes'
            if move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                return 'Transacciones de Juegos' if 'juego' in journal_name.lower() else 'Facturación'
            jn = journal_name.lower()
            if any(x in jn for x in ('bank', 'cash', 'tesorer', 'banco', 'caja')):
                return 'Dep./Retiros'
            if any(x in jn for x in ('bonus', 'promo', 'bono')):
                return 'Saldo de Bonus'
            return 'Ajustes'

        def describe(move_dict):
            return (
                move_dict.get('ref')
                or move_dict.get('narration')
                or move_dict.get('name')
                or _('Movimiento contable')
            )

        def state_label(move_dict):
            return 'Completado' if move_dict.get('state') == 'posted' else 'Pendiente'

        balance = 0.0
        movements3 = []
        for m in data:
            amount = float(m.get('amount_total_signed') or 0.0)
            balance += amount

            date_val = m.get('date')
            date_str = date_val.date().isoformat() if isinstance(date_val, datetime) else date_val

            movements3.append({
                'date': date_str,
                'description': describe(m),
                'type_display': classify(m),
                'amount': round(amount, 2),
                'state': state_label(m),
                'balance': round(balance, 2),
            })


        #raise UserError(f'No se encontraron movimientos contables para el usuario.{movements}') 
        
        # Renderizamos usando tu template
        return request.render('casino_online.portal_movimientos', {
            'movements': movements3,
            'request': request,  # para que funcione request.params en el template
        })    
        
        
        
    @http.route('/my/medios_pagos', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_medios_pagos(self, **post):
        partner = request.env.user.partner_id

        PaymentProvider = request.env['payment.provider']
        ConfigModel = request.env['partner.payment.method.config'].sudo()

        if request.httprequest.method == 'POST':
            # Guardar configuración
            payment_methods = PaymentProvider.sudo().search([('state', '=', 'enabled')])

            for pm in payment_methods:
                for_deposit = bool(post.get(f'deposit_{pm.id}'))
                for_withdraw = bool(post.get(f'withdraw_{pm.id}'))

                # Buscar si ya existe configuración
                config = ConfigModel.search([('partner_id', '=', partner.id), ('payment_provider_id', '=', pm.id)], limit=1)
                vals = {
                    'for_deposit': for_deposit,
                    'for_withdraw': for_withdraw,
                }
                if config:
                    config.write(vals)
                else:
                    vals.update({
                        'partner_id': partner.id,
                        'payment_provider_id': pm.id,
                    })
                    ConfigModel.create(vals)

            return request.redirect('/my/medios_pagos')

        # GET: Mostrar formulario con configuraciones
        payment_methods = PaymentProvider.sudo().search([('state', '=', 'enabled')])

        # Para cada método de pago, adjuntamos la configuración del partner si existe
        for pm in payment_methods:
            pm.config = ConfigModel.search([('partner_id', '=', partner.id), ('payment_provider_id', '=', pm.id)], limit=1)

        return request.render('casino_online.portal_medios_pagos', {
            'payment_methods': payment_methods,
        })
        
    @http.route('/my/mis_limites', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_mis_limites(self, **post):
        partner = request.env.user.partner_id.sudo()

        if request.httprequest.method == 'POST':
            daily_limit = post.get('daily_limit')
            weekly_limit = post.get('weekly_limit')
            monthly_limit = post.get('monthly_limit')

            vals = {}
            if daily_limit is not None:
                vals['daily_deposit_limit'] = float(daily_limit)
            if weekly_limit is not None:
                vals['weekly_deposit_limit'] = float(weekly_limit)
            if monthly_limit is not None:
                vals['monthly_deposit_limit'] = float(monthly_limit)

            partner.write(vals)
            return request.redirect('/my/mis_limites')

        # GET request
        daily_limit = partner.daily_deposit_limit
        weekly_limit = partner.weekly_deposit_limit
        monthly_limit = partner.monthly_deposit_limit

        return request.render('casino_online.portal_mis_limites', {
            'daily_limit': daily_limit,
            'weekly_limit': weekly_limit,
            'monthly_limit': monthly_limit,
        })
        
    @http.route('/my/datos_bank', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_datos_bancarios(self, **post):
        partner = request.env.user.partner_id.sudo()

        if request.httprequest.method == 'POST':
            vals = {
                'account_number': post.get('account_number'),
                'bank_name': post.get('bank_name'),
                'account_type': post.get('account_type'),
                'cbu': post.get('cbu'),
                'cuil': post.get('cuil'),
                'nuevo_cbu': post.get('nuevo_cbu'),
            }
            partner.write(vals)
            return request.redirect('/my/datos_bank')

        # GET request: cargar valores actuales
        return request.render('casino_online.portal_datos_bancarios', {
            'account_number': partner.account_number,
            'bank_name': partner.bank_name,
            'account_type': partner.account_type,
            'cbu': partner.cbu,
            'cuil': partner.cuil,
            'nuevo_cbu': partner.nuevo_cbu,
        })
        
    @http.route('/my/depositar', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_depositar(self, **post):
        if request.httprequest.method == 'POST':
            amount = post.get('amount')
            payment_provider_id = post.get('payment_provider_id')

            if not amount or not payment_provider_id:
                return request.redirect('/my/depositar')

            # Aquí podrías registrar el depósito si tienes un modelo
            request.env['portal.deposito'].sudo().create({
                'partner_id': request.env.user.partner_id.id,
                'amount': float(amount),
                'payment_provider_id': int(payment_provider_id),
            })

            return request.redirect('/my')

        # Cargar métodos de pago habilitados
        payment_methods = request.env['payment.provider'].sudo().search([
            ('state', '=', 'test'),('is_published', '=', True)
        ])

        return request.render('casino_online.portal_depositar_form', {
            'payment_providers': payment_methods,
        })

    @http.route('/my/depositar', type='http', auth='user', methods=['POST'], website=True)
    def portal_depositar_submit(self, **post):
        # Aquí procesas los datos enviados por el formulario
        amount = post.get('amount')
        # Validar y guardar en base de datos, etc.
        # Luego redirigir o mostrar mensaje
        return request.redirect('/my/confirmacion_deposito')
    
    @http.route('/my/retirar', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_retirar(self, **post):
        if http.request.httprequest.method == 'POST':
            amount = post.get('amount')
            payment_provider_id = post.get('payment_provider_id')

            # Validaciones básicas
            if not amount or not payment_provider_id:
                return request.redirect('/my/retirar')  # o renderizar con error

            # Aquí podrías registrar el retiro en un modelo personalizado
            request.env['portal.retiro'].sudo().create({
                'partner_id': request.env.user.partner_id.id,
                'amount': float(amount),
                'payment_provider_id': int(payment_provider_id),
            })

            return request.redirect('/my')  # o a una página de confirmación

        # GET request: mostrar el formulario
        payment_methods = request.env['payment.provider'].sudo().search([
            ('state', '=', 'test'),
            ('is_published', '=', True)
        ])
        return request.render('casino_online.portal_retirar_form', {
            'payment_providers': payment_methods,
        })

    @http.route('/my/registrar_bonus', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_registrar_bonus(self, **post):
        if request.httprequest.method == 'POST':
            promo_code = post.get('promo_code')

            if not promo_code:
                return request.redirect('/my/registrar_bonus')

            # Registrar el bonus si tienes un modelo (opcional)
            request.env['portal.bonus'].sudo().create({
                'partner_id': request.env.user.partner_id.id,
                'code': promo_code,
            })

            return request.redirect('/my')  # o a una página de confirmación

        return request.render('casino_online.portal_registrar_bonus_form')