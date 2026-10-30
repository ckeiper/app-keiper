"""Fair selection of never-read or stale visit data for bounded background batches."""
REFRESH_HOURS = 6
DUE_STORE_SQL = """
    SELECT c.id FROM conexoes c
    JOIN anuncios a ON a.conexao_id=c.id AND a.status='active'
        AND a.item_id ~ '^MLB[0-9]+$'
    LEFT JOIN item_visits_checked v ON v.conexao_id=a.conexao_id AND v.item_id=a.item_id
    WHERE c.status='ativa' AND c.access_token IS NOT NULL
    GROUP BY c.id
    HAVING COUNT(*) FILTER (WHERE v.consultado_em IS NULL
        OR v.consultado_em <= NOW() - (%s * INTERVAL '1 hour')) > 0
    ORDER BY (COUNT(*) FILTER (WHERE v.consultado_em IS NULL) > 0) DESC,
        MIN(v.consultado_em) ASC NULLS FIRST,c.id
    LIMIT 1
"""
