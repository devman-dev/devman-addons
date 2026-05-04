def migrate(cr, version):
    cr.execute(
        """
        UPDATE pf_gateway_user
           SET parent_company_gateway_user_id = NULL
         WHERE parent_company_gateway_user_id IS NOT NULL
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'pagoflex_wallet_gateway'
           AND name = 'incoming_transfer_commission_settings_default'
           AND model = 'pf.gateway.incoming.transfer.commission.settings'
        """
    )
    cr.execute(
        """
        DELETE FROM pf_gateway_incoming_transfer_commission_settings
         WHERE COALESCE(app_name, '') = ''
           AND COALESCE(gateway_setting_id, 0) = 0
           AND COALESCE(default_percentage, 0) = 0
           AND is_active IS FALSE
        """
    )
    cr.execute(
        """
        DO $$
        DECLARE
            constraint_name text;
        BEGIN
            FOR constraint_name IN
                SELECT con.conname
                  FROM pg_constraint con
                  JOIN pg_class rel ON rel.oid = con.conrelid
                  JOIN pg_attribute att ON att.attrelid = rel.oid
                                      AND att.attnum = ANY(con.conkey)
                 WHERE rel.relname = 'pf_gateway_incoming_transfer_commission_distribution_rule'
                   AND con.contype = 'u'
                   AND att.attname = 'gateway_rule_id'
            LOOP
                EXECUTE format(
                    'ALTER TABLE pf_gateway_incoming_transfer_commission_distribution_rule DROP CONSTRAINT IF EXISTS %I',
                    constraint_name
                );
            END LOOP;
        END $$;
        """
    )
