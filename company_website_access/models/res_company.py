from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import webbrowser
import qrcode
from qrcode.image.pil import PilImage
import io
import base64
from PIL import Image, ImageDraw


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

    # Campo checkbox para incluir logo en QR
    include_logo_in_qr = fields.Boolean(
        string='Incluir Logo en QR',
        default=True,
        help='Marcar para incluir el logo de la empresa en el centro del código QR'
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
        
    @api.depends('custom_website_link', 'include_logo_in_qr', 'logo')
    def _compute_website_qr_code(self):
        """Genera el código QR basado en el enlace del website"""
        for record in self:
            if record.custom_website_link:
                try:
                    # Crear el objeto QR
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=20,
                        border=4,
                    )
                    
                    # Asegurar que la URL tenga protocolo
                    url = record.custom_website_link
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    
                    qr.add_data(url)
                    qr.make(fit=True)

                    # Crear la imagen
                    img = qr.make_image(
                        fill_color="#000000", 
                        back_color="#FFFFFF",
                        image_factory=qrcode.image.pil.PilImage
                    )
                    
                    # Redimensionar para optimizar calidad vs tamaño
                    # Crear imagen de alta resolución y luego redimensionar con antialiasing
                    from PIL import Image
                    
                    # Convertir a PIL Image si no lo es ya
                    if hasattr(img, '_img'):
                        pil_img = img._img
                    else:
                        pil_img = img
                    
                    # Crear una versión de alta resolución (800x800) y luego redimensionar
                    high_res_size = (800, 800)
                    if pil_img.size != high_res_size:
                        # Redimensionar manteniendo aspecto y usando LANCZOS para mejor calidad
                        pil_img = pil_img.resize(high_res_size, Image.Resampling.LANCZOS)
                    
                    # Agregar logo de la empresa en el centro si existe
                    if record.include_logo_in_qr and record.logo:
                        try:
                            # Decodificar el logo de la empresa
                            logo_data = base64.b64decode(record.logo)
                            logo_buffer = io.BytesIO(logo_data)
                            logo_img = Image.open(logo_buffer)
                            
                            # Convertir a RGBA si no lo es
                            if logo_img.mode != 'RGBA':
                                logo_img = logo_img.convert('RGBA')
                            
                            # Calcular el tamaño del logo (15% del QR)
                            qr_size = pil_img.size[0]
                            logo_size = int(qr_size * 0.15)
                            
                            # Redimensionar el logo manteniendo aspecto
                            logo_img.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
                            
                            # Crear un fondo blanco circular para el logo
                            mask_size = logo_img.size[0] + 20  # 10px de padding por cada lado
                            mask = Image.new('RGBA', (mask_size, mask_size), (255, 255, 255, 255))
                            
                            # Crear máscara circular
                            from PIL import ImageDraw
                            draw = ImageDraw.Draw(mask)
                            draw.ellipse([0, 0, mask_size, mask_size], fill=(255, 255, 255, 255), outline=None)
                            
                            # Pegar el logo en el centro de la máscara
                            logo_pos = ((mask_size - logo_img.size[0]) // 2, 
                                       (mask_size - logo_img.size[1]) // 2)
                            mask.paste(logo_img, logo_pos, logo_img)
                            
                            # Calcular posición central en el QR
                            qr_center = (qr_size // 2, qr_size // 2)
                            paste_pos = (qr_center[0] - mask_size // 2, 
                                        qr_center[1] - mask_size // 2)
                            
                            # Convertir QR a RGBA para permitir transparencias
                            if pil_img.mode != 'RGBA':
                                pil_img = pil_img.convert('RGBA')
                            
                            # Pegar la máscara con logo en el QR
                            pil_img.paste(mask, paste_pos, mask)
                            
                        except Exception as e:
                            # Si hay error con el logo, continuar sin él
                            pass
                            
                    # Convertir a base64
                    buffer = io.BytesIO()
                    # Convertir de vuelta a RGB para PNG si está en RGBA
                    if pil_img.mode == 'RGBA':
                        # Crear fondo blanco
                        background = Image.new('RGB', pil_img.size, (255, 255, 255))
                        background.paste(pil_img, mask=pil_img.split()[-1])  # Usar canal alpha como máscara
                        pil_img = background
                    elif pil_img.mode != 'RGB':
                        pil_img = pil_img.convert('RGB')
                        
                    pil_img.save(buffer, format='PNG', optimize=True, quality=95)
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
        logo_suffix = "_con_logo" if self.include_logo_in_qr and self.logo else ""  
        filename = f"QR_{company_name}{logo_suffix}.png"
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=res.company&id={self.id}&field=website_qr_code&download=true&filename={filename}',
            'target': 'self',
        }