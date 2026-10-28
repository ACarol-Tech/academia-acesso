"""Acesso ao MySQL com Pool de Conexões. Todas as consultas usam parâmetros (%s): nunca monte SQL com f-string."""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pymysql
import pymysql.cursors
from dbutils.pooled_db import PooledDB

from .config import settings


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def novo_id() -> str:
    return str(uuid.uuid4())


# Criando o Pool de Conexões (mantém conexões abertas e prontas para uso)
pool = PooledDB(
    creator=pymysql,
    maxconnections=10,   # Número máximo de conexões simultâneas no pool
    mincached=2,         # Conexões mínimas mantidas prontas em cache
    maxcached=5,         # Conexões máximas em cache
    blocking=True,       # Aguarda uma conexão ficar livre se o pool estiver esgotado
    host=settings.db_host,
    port=settings.db_port,
    user=settings.db_user,
    password=settings.db_password,
    database=settings.db_name,
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor
)


@contextmanager
def transacao():
    # Pega uma conexão pronta do pool em vez de abrir uma nova do zero
    cx = pool.connection()
    try:
        with cx.cursor() as cur:
            yield cur
        cx.commit()
    except Exception:
        cx.rollback()
        raise
    finally:
        # No DBUtils, o .close() devolve a conexão para o pool (não fecha o socket físico)
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