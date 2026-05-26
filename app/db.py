import os
import sqlite3
from pathlib import Path

import httpx

INITIAL_STATUSES: dict[str, str] = {
    "azure-databricks": "done",
    "adls-gen2": "done",
    "unity-catalog": "done",
    "delta-lake": "done",
    "medallion": "done",
    "unity-catalog-volumes": "done",
    "auto-loader": "done",
    "lakeflow-jobs": "done",
    "ai-parse-document": "done",
    "mosaic-ai-agent-framework": "done",
    "unity-ai-gateway": "done",
    "foundation-model-apis": "todo",
    "model-serving": "todo",
    "langgraph-langchain": "todo",
    "multi-agent": "todo",
    "vector-search": "todo",
    "rag": "todo",
    "byo-embeddings": "todo",
    "databricks-apps": "todo",
    "mlflow": "todo",
    "databricks-asset-bundles": "todo",
    "lakeview-dashboard": "todo",
    "system-tables": "todo",
}

VALID_STATUSES = frozenset({"todo", "in_progress", "done"})

_DB_PATH = Path(__file__).parent / "status.db"


def _use_turso() -> bool:
    return bool(os.getenv("TURSO_URL") and os.getenv("TURSO_AUTH_TOKEN"))


def _turso_pipeline(requests: list) -> list:
    url = os.environ["TURSO_URL"].replace("libsql://", "https://")
    token = os.environ["TURSO_AUTH_TOKEN"]
    resp = httpx.post(
        f"{url}/v2/pipeline",
        headers={"Authorization": f"Bearer {token}"},
        json={"requests": requests},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["results"]


def _stmt(sql: str, args: list[str] = ()) -> dict:
    return {
        "type": "execute",
        "stmt": {
            "sql": sql,
            "args": [{"type": "text", "value": str(a)} for a in args],
        },
    }


def _turso_rows(sql: str, args: list[str] = ()) -> list[list[str]]:
    results = _turso_pipeline([_stmt(sql, args), {"type": "close"}])
    rows_raw = results[0]["response"]["result"]["rows"]
    return [[cell["value"] for cell in row] for row in rows_raw]


def _turso_batch(statements: list[tuple[str, list[str]]]) -> None:
    requests = [_stmt(sql, args) for sql, args in statements] + [{"type": "close"}]
    _turso_pipeline(requests)


def init_db() -> None:
    create = (
        """
        CREATE TABLE IF NOT EXISTS card_status (
            card_id TEXT PRIMARY KEY,
            status  TEXT NOT NULL DEFAULT 'todo'
                      CHECK(status IN ('todo', 'in_progress', 'done'))
        )
        """,
        [],
    )
    inserts = [
        ("INSERT OR IGNORE INTO card_status (card_id, status) VALUES (?, ?)", [cid, st])
        for cid, st in INITIAL_STATUSES.items()
    ]

    if _use_turso():
        _turso_batch([create] + inserts)
    else:
        conn = sqlite3.connect(_DB_PATH)
        conn.execute(create[0])
        for sql, args in inserts:
            conn.execute(sql, args)
        conn.commit()


def get_all_statuses() -> dict[str, str]:
    sql = "SELECT card_id, status FROM card_status"
    if _use_turso():
        rows = _turso_rows(sql)
    else:
        rows = sqlite3.connect(_DB_PATH).execute(sql).fetchall()
    return {row[0]: row[1] for row in rows}


def update_status(card_id: str, status: str) -> bool:
    if card_id not in INITIAL_STATUSES:
        return False
    sql = "UPDATE card_status SET status = ? WHERE card_id = ?"
    if _use_turso():
        _turso_batch([(sql, [status, card_id])])
    else:
        conn = sqlite3.connect(_DB_PATH)
        conn.execute(sql, (status, card_id))
        conn.commit()
    return True
