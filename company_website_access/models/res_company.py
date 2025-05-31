from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import webbrowser
import qrcode
import io
import base64

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Campo para el enlace personalizado
    custom_website_link = fields.Char(
        string='Enlace del Website',
        help='URL personalizada para esta compañía'
    )
    
    # Campo para notas alternativas
    website_notes = fields.Text(
        string='Notas Alternativas',
        help='Notas adicionales sobre el website de la compañía'
    )

    # Campo para el QR del enlace
    website_qr_code = fields.Binary(
        string='Código QR',
        compute='_compute_website_qr_code',
        store=False,
        help='Código QR generado automáticamente del enlace del website'
    )
    
    def action_test_link(self):
        """Acción para probar el enlace personalizado"""
        self.ensure_one()
        if not self.custom_website_link:
            raise UserError("No hay enlace configurado para probar.")
        
        # Verificar si la URL tiene el protocolo
        url = self.custom_website_link
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
            
        try:
            # Intentar hacer una petición HEAD para verificar si el enlace es válido
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return {
                    'type': 'ir.actions.act_url',
                    'url': url,
                    'target': 'new',
                }
            else:
                raise UserError(f"El enlace no es accesible. Código de respuesta: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error al probar el enlace: {str(e)}")

    def action_generate_company_url(self):
        """Genera una URL específica para la compañía basada en el website base"""
        self.ensure_one()
        
        # Obtener la URL base del website
        website = self.env['website'].search([('company_id', '=', self.id)], limit=1)
        if not website:
            website = self.env['website'].search([], limit=1)
            
        if not website:
            raise UserError("No se encontró ningún website configurado.")
            
        base_url = website.domain or self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        
        # Generar la URL con el ID de la compañía
        company_url = f"{base_url}?company_id={self.id}"

        # Actualizar el campo custom_website_link
        self.write({'custom_website_link': company_url})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.company',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': dict(self.env.context, active_tab='contact_tab'),
        }
        
    @api.depends('custom_website_link')
    def _compute_website_qr_code(self):
        """Genera el código QR basado en el enlace del website"""
        for record in self:
            if record.custom_website_link:
                try:
                    # Crear el objeto QR
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    
                    # Asegurar que la URL tenga protocolo
                    url = record.custom_website_link
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    
                    qr.add_data(url)
                    qr.make(fit=True)

                    # Crear la imagen
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # Convertir a base64
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    buffer.seek(0)
                    record.website_qr_code = base64.b64encode(buffer.getvalue())
                    
                except Exception:
                    record.website_qr_code = False
            else:
                record.website_qr_code = False

    def action_export_qr_code(self):
        """Exporta el código QR como archivo PNG"""
        self.ensure_one()
        if not self.custom_website_link:
            raise UserError("No hay enlace configurado para generar el código QR.")
        
        if not self.website_qr_code:
            raise UserError("No se pudo generar el código QR.")
        
        # Crear el nombre del archivo
        company_name = self.name.replace(' ', '_').replace('/', '_')
        filename = f"QR_{company_name}.png"
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=res.company&id={self.id}&field=website_qr_code&download=true&filename={filename}',
            'target': 'self',
        }
            
        