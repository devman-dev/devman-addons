# hooks.py
from odoo import api, SUPERUSER_ID

def create_bet_limits_for_all_partners(cr, registry=None):
    # Soporta llamada con cr solo, o cr+registry
    env = None
    try:
        # Si 'cr' es un Environment (raro, pero por las dudas)
        from odoo.api import Environment
        if hasattr(cr, "cr") and hasattr(cr, "uid"):
            env = cr
        else:
            # cr es cursor, armamos Environment con superusuario
            env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        # Fallback por si algo no encaja
        env = api.Environment(cr, SUPERUSER_ID, {})

    Partner = env['res.partner'].sudo()
    BetLimits = env['casino.game.bet.limits'].sudo()

    # Procesar en lotes por si hay muchos partners
    offset, batch = 0, 1000
    while True:
        partners = Partner.search([], offset=offset, limit=batch)
        if not partners:
            break
        for partner in partners:
            BetLimits.get_or_create_for_partner(partner)
        offset += batch


def recalculate_partner_roles(cr, registry=None):
    """Recalcula el campo 'role' para todos los partners que sean agentes o jugadores."""
    env = None
    try:
        from odoo.api import Environment
        if hasattr(cr, "cr") and hasattr(cr, "uid"):
            env = cr
        else:
            env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        env = api.Environment(cr, SUPERUSER_ID, {})

    Partner = env['res.partner'].sudo()
    
    # Buscar partners que sean agentes o jugadores
    partners = Partner.search([
        '|',
        ('is_agent', '=', True),
        ('is_player', '=', True)
    ])
    
    if partners:
        # Forzar recálculo del campo role
        partners._compute_role()
        print(f"✓ Campo 'role' recalculado para {len(partners)} partners")


def post_init_hook(cr, registry=None):
    """Hook que se ejecuta después de instalar o actualizar el módulo."""
    create_bet_limits_for_all_partners(cr, registry)
    recalculate_partner_roles(cr, registry)
