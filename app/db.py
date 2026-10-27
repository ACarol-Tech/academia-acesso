"""Acesso ao MySQL. Todas as consultas usam parâmetros (%s): nunca monte SQL com f-string."""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pymysql
import pymysql.cursors

from .config import settings


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def novo_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def transacao():
    cx = pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                         password=settings.db_password, database=settings.db_name,
                         charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with cx.cursor() as cur:
            yield cur
        cx.commit()
    except Exception:
        cx.rollback()
        raise
    finally:
        cx.close()


def consultar(sql: str, params: tuple = ()):
    with transacao() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def um(sql: str, params: tuple = ()):
    r = consultar(sql, params)
    return r[0] if r else None


def executar(sql: str, params: tuple = ()):
    with transacao() as cur:
        cur.execute(sql, params)
