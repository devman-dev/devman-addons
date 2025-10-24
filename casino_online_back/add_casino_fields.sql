-- SQL Script to add casino banking configuration fields to res_company table
-- Execute this in the PostgreSQL database if the migration doesn't work automatically

-- Add casino_deposit_journal_id column
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='res_company' AND column_name='casino_deposit_journal_id') THEN
        ALTER TABLE res_company ADD COLUMN casino_deposit_journal_id integer;
        ALTER TABLE res_company ADD CONSTRAINT res_company_casino_deposit_journal_id_fkey 
            FOREIGN KEY (casino_deposit_journal_id) REFERENCES account_journal(id) ON DELETE SET NULL;
        RAISE NOTICE 'Added casino_deposit_journal_id column';
    END IF;
END $$;

-- Add casino_bet_transfer_journal_id column
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='res_company' AND column_name='casino_bet_transfer_journal_id') THEN
        ALTER TABLE res_company ADD COLUMN casino_bet_transfer_journal_id integer;
        ALTER TABLE res_company ADD CONSTRAINT res_company_casino_bet_transfer_journal_id_fkey 
            FOREIGN KEY (casino_bet_transfer_journal_id) REFERENCES account_journal(id) ON DELETE SET NULL;
        RAISE NOTICE 'Added casino_bet_transfer_journal_id column';
    END IF;
END $$;

-- Add casino_deposit_account_id column
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='res_company' AND column_name='casino_deposit_account_id') THEN
        ALTER TABLE res_company ADD COLUMN casino_deposit_account_id integer;
        ALTER TABLE res_company ADD CONSTRAINT res_company_casino_deposit_account_id_fkey 
            FOREIGN KEY (casino_deposit_account_id) REFERENCES account_account(id) ON DELETE SET NULL;
        RAISE NOTICE 'Added casino_deposit_account_id column';
    END IF;
END $$;

-- Add casino_bet_account_id column
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='res_company' AND column_name='casino_bet_account_id') THEN
        ALTER TABLE res_company ADD COLUMN casino_bet_account_id integer;
        ALTER TABLE res_company ADD CONSTRAINT res_company_casino_bet_account_id_fkey 
            FOREIGN KEY (casino_bet_account_id) REFERENCES account_account(id) ON DELETE SET NULL;
        RAISE NOTICE 'Added casino_bet_account_id column';
    END IF;
END $$;