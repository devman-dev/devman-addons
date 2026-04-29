def migrate(cr, version):
    cr.execute(
        """
        UPDATE pf_gateway_user
           SET parent_company_gateway_user_id = NULL
         WHERE parent_company_gateway_user_id IS NOT NULL
        """
    )
