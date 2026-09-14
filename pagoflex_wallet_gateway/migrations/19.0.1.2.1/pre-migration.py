def migrate(cr, version):
    """Create stored computed/related columns before the registry can query them.

    This is intentionally defensive: some deployments reload Python code before
    the regular ORM schema synchronization finishes, allowing scheduled jobs to
    observe the new field definitions against the previous database schema.
    """
    cr.execute(
        """
        ALTER TABLE pf_gateway_user
            ADD COLUMN IF NOT EXISTS cuit_cuil_or_dni varchar,
            ADD COLUMN IF NOT EXISTS cuit_cuil_or_dni_display varchar
        """
    )
    cr.execute(
        """
        UPDATE pf_gateway_user
           SET cuit_cuil_or_dni = COALESCE(NULLIF(cuit_cuil, ''), NULLIF(dni, '')),
               cuit_cuil_or_dni_display = CASE
                   WHEN COALESCE(NULLIF(cuit_cuil, ''), NULLIF(dni, '')) IS NOT NULL
                    AND NULLIF(full_name, '') IS NOT NULL
                       THEN COALESCE(NULLIF(cuit_cuil, ''), NULLIF(dni, '')) || ' - ' || full_name
                   ELSE COALESCE(
                       NULLIF(cuit_cuil, ''),
                       NULLIF(dni, ''),
                       NULLIF(full_name, '')
                   )
               END
        """
    )
    cr.execute(
        """
        ALTER TABLE pf_gateway_transfer
            ADD COLUMN IF NOT EXISTS source_user_cuit_cuil_or_dni varchar,
            ADD COLUMN IF NOT EXISTS source_user_cuit_cuil_or_dni_display varchar,
            ADD COLUMN IF NOT EXISTS destination_user_cuit_cuil_or_dni varchar,
            ADD COLUMN IF NOT EXISTS destination_user_cuit_cuil_or_dni_display varchar
        """
    )
    cr.execute(
        """
        UPDATE pf_gateway_transfer transfer
           SET source_user_cuit_cuil_or_dni = source_user.cuit_cuil_or_dni,
               source_user_cuit_cuil_or_dni_display = source_user.cuit_cuil_or_dni_display
          FROM pf_gateway_user source_user
         WHERE source_user.id = transfer.source_user_id
        """
    )
    cr.execute(
        """
        UPDATE pf_gateway_transfer transfer
           SET destination_user_cuit_cuil_or_dni = destination_user.cuit_cuil_or_dni,
               destination_user_cuit_cuil_or_dni_display = destination_user.cuit_cuil_or_dni_display
          FROM pf_gateway_user destination_user
         WHERE destination_user.id = transfer.destination_user_id
        """
    )
