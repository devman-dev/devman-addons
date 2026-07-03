WITH params AS (
    SELECT
        DATE '2026-06-10' AS target_date,
        'America/Argentina/Buenos_Aires'::text AS tz,
        TIME '21:00:00' AS time_from,
        TIME '23:59:59.999999' AS time_to
),
wallet_cvus AS (
    SELECT cvu_cbu
    FROM pf_gateway_bank_account
    WHERE cvu_cbu IS NOT NULL
      AND cvu_cbu <> ''
)
SELECT COUNT(*) AS wallet_in_count,
       COALESCE(SUM(t.amount), 0) AS wallet_in_amount
FROM pf_gateway_transfer t
CROSS JOIN params p
WHERE t.active IS TRUE
  AND COALESCE(UPPER(t.status), '') <> 'FAILED'
  AND t.movement_nature = 'TRANSFER'
  AND t.source_address IS NOT NULL
  AND t.source_address <> ''
  AND (
      t.fecha_negocio = p.target_date
      OR (
          t.fecha_negocio IS NULL
          AND ((t.transaction_at AT TIME ZONE 'UTC' AT TIME ZONE p.tz)::date = p.target_date)
      )
  )
  AND ((t.transaction_at AT TIME ZONE 'UTC' AT TIME ZONE p.tz)::time BETWEEN p.time_from AND p.time_to)
  AND (
      t.destination_bank_account_id IS NOT NULL
      OR t.destination_address IN (SELECT cvu_cbu FROM wallet_cvus)
  )
  AND t.source_bank_account_id IS NULL
  AND t.source_address NOT IN (SELECT cvu_cbu FROM wallet_cvus);