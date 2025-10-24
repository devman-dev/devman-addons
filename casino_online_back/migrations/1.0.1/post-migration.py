"""
Migration script to add casino banking configuration fields to res.company
"""

def migrate(cr, version):
    """Add new casino banking fields to res_company table"""
    
    # Check if columns exist before adding them
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='res_company' 
        AND column_name IN (
            'casino_deposit_journal_id',
            'casino_bet_transfer_journal_id', 
            'casino_deposit_account_id',
            'casino_bet_account_id'
        )
    """)
    
    existing_columns = [row[0] for row in cr.fetchall()]
    
    # Add casino_deposit_journal_id if it doesn't exist
    if 'casino_deposit_journal_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN casino_deposit_journal_id integer
        """)
        print("Added column casino_deposit_journal_id to res_company")
    
    # Add casino_bet_transfer_journal_id if it doesn't exist
    if 'casino_bet_transfer_journal_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN casino_bet_transfer_journal_id integer
        """)
        print("Added column casino_bet_transfer_journal_id to res_company")
    
    # Add casino_deposit_account_id if it doesn't exist
    if 'casino_deposit_account_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN casino_deposit_account_id integer
        """)
        print("Added column casino_deposit_account_id to res_company")
    
    # Add casino_bet_account_id if it doesn't exist
    if 'casino_bet_account_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN casino_bet_account_id integer
        """)
        print("Added column casino_bet_account_id to res_company")
    
    # Add foreign key constraints if the columns were just created
    if 'casino_deposit_journal_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD CONSTRAINT res_company_casino_deposit_journal_id_fkey 
            FOREIGN KEY (casino_deposit_journal_id) 
            REFERENCES account_journal(id) 
            ON DELETE SET NULL
        """)
    
    if 'casino_bet_transfer_journal_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD CONSTRAINT res_company_casino_bet_transfer_journal_id_fkey 
            FOREIGN KEY (casino_bet_transfer_journal_id) 
            REFERENCES account_journal(id) 
            ON DELETE SET NULL
        """)
    
    if 'casino_deposit_account_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD CONSTRAINT res_company_casino_deposit_account_id_fkey 
            FOREIGN KEY (casino_deposit_account_id) 
            REFERENCES account_account(id) 
            ON DELETE SET NULL
        """)
    
    if 'casino_bet_account_id' not in existing_columns:
        cr.execute("""
            ALTER TABLE res_company 
            ADD CONSTRAINT res_company_casino_bet_account_id_fkey 
            FOREIGN KEY (casino_bet_account_id) 
            REFERENCES account_account(id) 
            ON DELETE SET NULL
        """)
    
    print("Migration completed: Added casino banking configuration fields to res_company")