#!/usr/bin/env python3
"""
Script para recalcular el campo 'role' en res.partner.
Ejecutar desde la línea de comandos de Odoo shell:

odoo-bin shell -d nombre_base_datos --addons-path=/ruta/addons

Luego ejecutar:
exec(open('recalculate_role.py').read())
"""

# Buscar todos los partners que sean agentes o jugadores
partners = env['res.partner'].search([
    '|',
    ('is_agent', '=', True),
    ('is_player', '=', True)
])

print(f"Encontrados {len(partners)} partners para recalcular...")

# Forzar recálculo del campo role
partners._compute_role()

print(f"✓ Campo 'role' recalculado para {len(partners)} partners")

# Verificar resultados
agents = partners.filtered(lambda p: p.role == 'agent')
players = partners.filtered(lambda p: p.role == 'player')

print(f"  - Agentes: {len(agents)}")
print(f"  - Jugadores: {len(players)}")
