"""
Run PostgreSQL VACUUM ANALYZE.
"""
def execute(table_name: str = 'public') -> tuple[bool, str]:
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='postgres', user='postgres')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f'VACUUM ANALYZE')
        cur.close()
        conn.close()
        return True, f"VACUUM ANALYZE completed"
    except Exception as e:
        return False, str(e)