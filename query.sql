
DO $$
DECLARE
    t text;
    c text;
    cnt integer;
    total integer := 0;
BEGIN
    FOR t IN 
        SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'
    LOOP
        SELECT column_name INTO c FROM information_schema.columns 
        WHERE table_name = t AND data_type LIKE '%timestamp%' LIMIT 1;
        
        IF c IS NOT NULL THEN
            EXECUTE format('SELECT count(*) FROM %I WHERE DATE(%I) = %L', t, c, '2026-07-28') INTO cnt;
            IF cnt > 0 THEN
                RAISE NOTICE 'Table %: % rows', t, cnt;
                total := total + cnt;
            END IF;
        END IF;
    END LOOP;
    RAISE NOTICE 'Total rows saved today: %', total;
END;
;

