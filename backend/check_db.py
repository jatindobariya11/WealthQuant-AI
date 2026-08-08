import psycopg2

try:
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        database="wealthquant",
        user="wealthquant",
        password="wealthquant",
    )
    cur = conn.cursor()

    # Get all tables
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    tables = [r[0] for r in cur.fetchall()]

    total_tables = len(tables)
    total_rows = 0
    today_rows = 0
    table_sizes = []

    for t in tables:
        # get total rows
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        total_rows += cnt
        table_sizes.append((t, cnt))

        # get timestamp columns
        cur.execute(
            f"SELECT column_name FROM information_schema.columns WHERE table_name = '{t}' AND data_type LIKE '%timestamp%' LIMIT 1"
        )
        col = cur.fetchone()
        if col:
            cur.execute(f"SELECT COUNT(*) FROM {t} WHERE DATE({col[0]}) = CURRENT_DATE")
            tc = cur.fetchone()[0]
            today_rows += tc

    table_sizes.sort(key=lambda x: x[1], reverse=True)

    print(f"Total Tables: {total_tables}")
    print(f"Total Rows: {total_rows}")
    print(f"Today's New Rows: {today_rows}")
    print(f"Largest Tables: {table_sizes[:5]}")
    print("Connection Status: PASS")

except Exception as e:
    print(f"Error: {e}")
