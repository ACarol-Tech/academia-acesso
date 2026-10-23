"""Acesso ao MySQL. Todas as consultas usam parâmetros (%s): nunca monte SQL com f-string."""
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pymysql
import pymysql.cursors

from .config import settings

# O sistema inteiro usa o horário de Belém (sem horário de verão), para que banco,
# painel e relatórios concordem sobre o que é "hoje".
FUSO = ZoneInfo("America/Belem")


def agora() -> datetime:
    return datetime.now(FUSO).replace(tzinfo=None)


def data_hoje() -> date:
    return agora().date()


def novo_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def transacao():
    cx = pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                         password=settings.db_password, database=settings.db_name,
                         charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                         init_command="SET time_zone = '-03:00'")
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