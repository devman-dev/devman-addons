# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CollectionReportsAPI(http.Controller):
    """API para reportes y analytics"""
    
    def _validate_auth(self):
        """Validar autenticación del usuario"""
        if not request.env.user or request.env.user._is_public():
            return self._error_response(401, "UNAUTHORIZED", "Autenticación requerida")
        return None
    
    def _success_response(self, data, message="Success"):
        """Respuesta exitosa estándar"""
        return {
            "success": True,
            "data": data,
            "message": message
        }
    
    def _error_response(self, status_code, error_code, message, details=None):
        """Respuesta de error estándar"""
        error_data = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message
            }
        }
        if details:
            error_data["error"]["details"] = details
        
        return error_data
    
    # ==================== ENDPOINTS DE REPORTES ====================
    
    @http.route('/api/collection/reports/transactions', type='json', auth='user', methods=['POST'], csrf=False)
    def generate_transaction_report(self, **kwargs):
        """Generar reporte de transacciones"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Validar parámetros requeridos
            if 'customer_id' not in kwargs:
                return self._error_response(400, "MISSING_FIELD", "Campo requerido: customer_id")
            
            customer = request.env['res.partner'].sudo().browse(kwargs['customer_id'])
            if not customer.exists():
                return self._error_response(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")
            
            # Obtener fechas
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            report_format = kwargs.get('format', 'pdf')
            
            if not date_from or not date_to:
                return self._error_response(400, "MISSING_DATES", "Se requieren date_from y date_to")
            
            # Buscar transacciones del cliente en el rango de fechas
            domain = [
                ('customer', '=', customer.id),
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ]
            
            transactions = request.env['collection.transaction'].sudo().search(domain)
            
            if not transactions:
                return self._error_response(404, "NO_TRANSACTIONS", "No se encontraron transacciones en el período")
            
            # Llamar al método print_report del modelo
            try:
                report_action = transactions.print_report()
                
                # Construir URL del reporte
                report_url = f"/web/content/ir.attachment/{report_action.get('context', {}).get('attachment_id', '')}/datas"
                
                return self._success_response({
                    "report_url": report_url,
                    "format": report_format,
                    "customer_id": customer.id,
                    "customer_name": customer.name,
                    "date_from": date_from,
                    "date_to": date_to,
                    "transaction_count": len(transactions),
                    "expires_at": (datetime.now().replace(hour=23, minute=59, second=59)).isoformat()
                }, "Reporte generado exitosamente")
                
            except Exception as report_error:
                _logger.error("Error generating report: %s", str(report_error))
                return self._error_response(500, "REPORT_ERROR", "Error al generar el reporte")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error in generate_transaction_report: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/reports/balance-summary', type='json', auth='user', methods=['GET'], csrf=False)
    def get_balance_summary(self, **kwargs):
        """Obtener resumen de saldos por cliente"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Construir dominio para clientes
            customer_domain = [('check_origin_account', '!=', True)]
            
            if 'customer_id' in kwargs:
                customer_domain.append(('id', '=', kwargs['customer_id']))
            
            customers = request.env['res.partner'].sudo().search(customer_domain)
            
            summary_data = []
            
            for customer in customers:
                # Obtener dashboard del cliente
                dashboard = request.env['collection.dashboard.customer'].sudo().search(
                    [('customer', '=', customer.id)], limit=1
                )
                
                if dashboard:
                    dashboard.update_available_balance()
                
                # Calcular transacciones por tipo
                transactions = request.env['collection.transaction'].sudo().search([
                    ('customer', '=', customer.id)
                ])
                
                acreditaciones = transactions.filtered(lambda t: t.collection_trans_type == 'movimiento_recaudacion')
                retiros = transactions.filtered(lambda t: t.collection_trans_type == 'retiro')
                internos = transactions.filtered(lambda t: t.collection_trans_type == 'movimiento_interno')
                
                customer_data = {
                    "customer_id": customer.id,
                    "customer_name": customer.name,
                    "customer_vat": customer.vat or "",
                    "balances": {
                        "total_balance": dashboard.customer_total_balance if dashboard else 0.0,
                        "available_balance": dashboard.customer_available_balance if dashboard else 0.0,
                        "real_balance": dashboard.customer_real_balance if dashboard else 0.0
                    },
                    "transaction_summary": {
                        "total_count": len(transactions),
                        "acreditaciones": {
                            "count": len(acreditaciones),
                            "total_amount": sum(t.amount for t in acreditaciones)
                        },
                        "retiros": {
                            "count": len(retiros),
                            "total_amount": sum(t.amount for t in retiros)
                        },
                        "internos": {
                            "count": len(internos),
                            "total_amount": sum(t.amount for t in internos)
                        }
                    },
                    "last_transaction_date": max(t.date for t in transactions).isoformat() if transactions else None
                }
                
                summary_data.append(customer_data)
            
            return self._success_response({
                "customers": summary_data,
                "total_customers": len(summary_data),
                "generated_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            _logger.error("Error in get_balance_summary: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/reports/transaction-analytics', type='json', auth='user', methods=['GET'], csrf=False)
    def get_transaction_analytics(self, **kwargs):
        """Obtener analytics de transacciones"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Parámetros opcionales
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            customer_id = kwargs.get('customer_id')
            
            # Construir dominio base
            domain = []
            
            if date_from:
                domain.append(('date', '>=', date_from))
            
            if date_to:
                domain.append(('date', '<=', date_to))
            
            if customer_id:
                domain.append(('customer', '=', customer_id))
            
            # Obtener todas las transacciones
            transactions = request.env['collection.transaction'].sudo().search(domain)
            
            # Analytics por tipo de transacción
            analytics_by_type = {}
            for trans_type in ['movimiento_recaudacion', 'retiro', 'movimiento_interno']:
                filtered_trans = transactions.filtered(lambda t: t.collection_trans_type == trans_type)
                analytics_by_type[trans_type] = {
                    "count": len(filtered_trans),
                    "total_amount": sum(t.amount for t in filtered_trans),
                    "average_amount": sum(t.amount for t in filtered_trans) / len(filtered_trans) if filtered_trans else 0
                }
            
            # Analytics por estado
            analytics_by_state = {}
            for state in ['aprobado', 'pendiente', 'rechazado', 'interno']:
                filtered_trans = transactions.filtered(lambda t: t.transaction_state == state)
                analytics_by_state[state] = {
                    "count": len(filtered_trans),
                    "total_amount": sum(t.amount for t in filtered_trans)
                }
            
            # Analytics por moneda
            analytics_by_currency = {}
            currencies = transactions.mapped('currency_id')
            for currency in currencies:
                filtered_trans = transactions.filtered(lambda t: t.currency_id.id == currency.id)
                analytics_by_currency[currency.name] = {
                    "count": len(filtered_trans),
                    "total_amount": sum(t.amount for t in filtered_trans),
                    "currency_symbol": currency.symbol
                }
            
            # Top clientes por volumen
            customer_analytics = {}
            customers = transactions.mapped('customer')
            for customer in customers:
                customer_trans = transactions.filtered(lambda t: t.customer.id == customer.id)
                customer_analytics[customer.name] = {
                    "customer_id": customer.id,
                    "transaction_count": len(customer_trans),
                    "total_amount": sum(t.amount for t in customer_trans),
                    "vat": customer.vat or ""
                }
            
            # Ordenar clientes por volumen
            sorted_customers = sorted(
                customer_analytics.items(),
                key=lambda x: x[1]['total_amount'],
                reverse=True
            )[:10]  # Top 10
            
            # Analytics temporales (por mes)
            monthly_analytics = {}
            for transaction in transactions:
                if transaction.date:
                    month_key = transaction.date.strftime('%Y-%m')
                    if month_key not in monthly_analytics:
                        monthly_analytics[month_key] = {
                            "count": 0,
                            "total_amount": 0,
                            "by_type": {
                                "movimiento_recaudacion": {"count": 0, "amount": 0},
                                "retiro": {"count": 0, "amount": 0},
                                "movimiento_interno": {"count": 0, "amount": 0}
                            }
                        }
                    
                    monthly_analytics[month_key]["count"] += 1
                    monthly_analytics[month_key]["total_amount"] += transaction.amount
                    monthly_analytics[month_key]["by_type"][transaction.collection_trans_type]["count"] += 1
                    monthly_analytics[month_key]["by_type"][transaction.collection_trans_type]["amount"] += transaction.amount
            
            return self._success_response({
                "summary": {
                    "total_transactions": len(transactions),
                    "total_amount": sum(t.amount for t in transactions),
                    "average_transaction": sum(t.amount for t in transactions) / len(transactions) if transactions else 0,
                    "date_range": {
                        "from": date_from,
                        "to": date_to
                    }
                },
                "by_transaction_type": analytics_by_type,
                "by_state": analytics_by_state,
                "by_currency": analytics_by_currency,
                "top_customers": [{"name": name, **data} for name, data in sorted_customers],
                "monthly_trends": monthly_analytics,
                "generated_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            _logger.error("Error in get_transaction_analytics: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/reports/commission-summary', type='json', auth='user', methods=['GET'], csrf=False)
    def get_commission_summary(self, **kwargs):
        """Obtener resumen de comisiones"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Parámetros opcionales
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            customer_id = kwargs.get('customer_id')
            
            # Construir dominio para comisiones
            domain = [('is_commission', '=', True)]
            
            if date_from:
                domain.append(('date', '>=', date_from))
            
            if date_to:
                domain.append(('date', '<=', date_to))
            
            if customer_id:
                domain.append(('customer', '=', customer_id))
            
            # Obtener comisiones
            commissions = request.env['collection.transaction'].sudo().search(domain)
            
            # Resumen general
            total_commission = sum(abs(c.amount) for c in commissions)
            commission_count = len(commissions)
            
            # Por cliente
            customer_commissions = {}
            customers = commissions.mapped('customer')
            
            for customer in customers:
                customer_comms = commissions.filtered(lambda c: c.customer.id == customer.id)
                customer_commissions[customer.name] = {
                    "customer_id": customer.id,
                    "commission_count": len(customer_comms),
                    "total_commission": sum(abs(c.amount) for c in customer_comms),
                    "average_commission": sum(abs(c.amount) for c in customer_comms) / len(customer_comms) if customer_comms else 0
                }
            
            # Por servicio
            service_commissions = {}
            services = commissions.mapped('service')
            
            for service in services:
                service_comms = commissions.filtered(lambda c: c.service.id == service.id)
                service_commissions[service.name_account] = {
                    "service_id": service.id,
                    "commission_count": len(service_comms),
                    "total_commission": sum(abs(c.amount) for c in service_comms),
                    "commission_rate": service.commission
                }
            
            return self._success_response({
                "summary": {
                    "total_commission": total_commission,
                    "commission_count": commission_count,
                    "average_commission": total_commission / commission_count if commission_count > 0 else 0,
                    "date_range": {
                        "from": date_from,
                        "to": date_to
                    }
                },
                "by_customer": customer_commissions,
                "by_service": service_commissions,
                "generated_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            _logger.error("Error in get_commission_summary: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
