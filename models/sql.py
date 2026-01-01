import psycopg as pg, os
from psycopg.rows import dict_row

#classe
class sql:
    def __init__(self):
        senha = os.getenv("postgres_password")
        self.config = {
            "host": "dpg-d5bb7nruibrs73cc73r0-a.ohio-postgres.render.com",
            "user": "andre",
            "password": senha,
            "dbname": "dbjetmoney_zy68",
            "port": 5432
        }

    def execute(self, query, params=None):
        # O 'with' fecha a conexão automaticamente ao final do bloco
        with pg.connect(**self.config, row_factory=dict_row) as conn: #** -> desempacota o dicionario
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount

    def search(self, query, params=None, one=False):
        with pg.connect(**self.config, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone() if one else cur.fetchall()