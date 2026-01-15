from odoo import models, fields, api


class CasinoExposureReportWizard(models.TransientModel):
    _name = 'casino.exposure.report.wizard'
    _description = 'Reporte de exposición por sesiones en curso'

    date_from = fields.Datetime(string='Desde')
    date_to = fields.Datetime(string='Hasta')
    provider_id = fields.Many2one('res.partner', string='Proveedor')

    line_ids = fields.One2many('casino.exposure.report.line', 'wizard_id', string='Exposición por jugador', readonly=True)

    def action_calculate(self):
        self.ensure_one()
        Session = self.env['casino.game.session']
        domain = []
        if self.date_from:
            domain.append(('start_datetime', '>=', self.date_from))
        if self.date_to:
            domain.append(('start_datetime', '<=', self.date_to))
        if self.provider_id:
            domain.append(('provider_id', '=', self.provider_id.id))

        # Limpiar líneas previas
        self.line_ids.unlink()

        # Buscar todas las sesiones y agrupar manualmente
        sessions = Session.search(domain)
        
        # Diccionario para acumular por (user_id, currency_id)
        aggregated = {}
        
        for session in sessions:
            key = (session.user_id.id, session.currency_id.id or self.env.company.currency_id.id)
            
            if key not in aggregated:
                aggregated[key] = {
                    'user_id': session.user_id.id,
                    'partner_id': session.user_id.partner_id.id,
                    'currency_id': key[1],
                    'sessions_count': 0,
                    'total_to_win': 0.0,
                    'company_profit': 0.0,
                }
            
            aggregated[key]['sessions_count'] += 1
            
            # Sumar to_win para sesiones win o cancelled
            if session.result in ('win', 'cancelled'):
                aggregated[key]['total_to_win'] += session.amount or 0.0
            else:
                # Sumar a ganancia de la empresa (sesiones que no son win ni cancelled)
                aggregated[key]['company_profit'] += session.amount or 0.0

        lines = []
        for data in aggregated.values():
            lines.append((0, 0, data))
        
        self.line_ids = lines
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'casino.exposure.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current'
        }


class CasinoExposureReportLine(models.TransientModel):
    _name = 'casino.exposure.report.line'
    _description = 'Línea de exposición por jugador'
    _order = 'total_to_win desc'

    wizard_id = fields.Many2one('casino.exposure.report.wizard', ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Jugador', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Contacto', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    sessions_count = fields.Integer(string='Sesiones en curso', readonly=True)
    total_to_win = fields.Monetary(string='A Pagar', currency_field='currency_id', readonly=True)
    company_profit = fields.Monetary(string='A Favor', currency_field='currency_id', readonly=True)
