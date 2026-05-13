"""
Simulates DB bloat by generating dead tuples.
Skips gracefully if PostgreSQL not available.
"""


class DbVacuumStarveScenario:
    def __init__(self):
        self.conn = None
        self.available = False
        self._check_postgres()

    def _check_postgres(self):
        try:
            import psycopg2
            self.conn = psycopg2.connect(dbname='postgres', user='postgres')
            self.available = True
        except:
            self.available = False

    def inject(self):
        if not self.available:
            print("PostgreSQL not available — skipping db_vacuum_starve")
            return
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS fault_bloat_test
            (id SERIAL PRIMARY KEY, data TEXT)
        ''')
        for i in range(1000):
            cur.execute("INSERT INTO fault_bloat_test (data) VALUES ('x')")
        self.conn.commit()
        cur.execute("DELETE FROM fault_bloat_test")
        self.conn.commit()
        cur.close()

    def cleanup(self):
        if not self.available:
            return
        cur = self.conn.cursor()
        cur.execute("DROP TABLE IF EXISTS fault_bloat_test")
        self.conn.commit()
        cur.close()
        self.conn.close()

    def verify_injected(self) -> bool:
        return self.available