"""app/data/pool.py

Thread-safe Connection Pool for CFO Copilot.
Enforces:
- Foundation Lock 3 (Crowd): Eliminates TCP socket handshake bottlenecks under concurrent load.
- Foundation Lock 6 (Partition): Connection checkout with automatic tenant context setting.
"""

from contextlib import contextmanager
from typing import Dict, Generator, Optional
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from app.core.config import get_settings

_POOLS: Dict[str, ThreadedConnectionPool] = {}


def get_connection_pool(role: str = "ro", is_test: bool = False) -> ThreadedConnectionPool:
    key = f"{role}_{'test' if is_test else 'prod'}"
    if key not in _POOLS:
        settings = get_settings()
        params = settings.get_connection_params(role=role, is_test=is_test)
        # 4 min connections, up to 32 max connections for 16 concurrent sessions
        _POOLS[key] = ThreadedConnectionPool(minconn=4, maxconn=32, **params)
    return _POOLS[key]


@contextmanager
def get_connection(
    role: str = "ro",
    is_test: bool = False,
    tenant_id: Optional[str] = None
) -> Generator[psycopg2.extensions.connection, None, None]:
    pool = get_connection_pool(role=role, is_test=is_test)
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            if tenant_id:
                cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
            else:
                cur.execute("RESET app.current_tenant;")
        yield conn
        if role == "rw":
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("RESET app.current_tenant;")
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)

