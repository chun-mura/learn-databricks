import os

import libsql_experimental as libsql

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


def _connect() -> libsql.Connection:
    url = os.getenv("TURSO_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    if url and token:
        return libsql.connect(database=url, auth_token=token)
    return libsql.connect("status.db")


def init_db() -> None:
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS card_status (
            card_id TEXT PRIMARY KEY,
            status  TEXT NOT NULL DEFAULT 'todo'
                      CHECK(status IN ('todo', 'in_progress', 'done'))
        )
    """)
    for card_id, status in INITIAL_STATUSES.items():
        conn.execute(
            "INSERT OR IGNORE INTO card_status (card_id, status) VALUES (?, ?)",
            (card_id, status),
        )
    conn.commit()


def get_all_statuses() -> dict[str, str]:
    conn = _connect()
    rows = conn.execute("SELECT card_id, status FROM card_status").fetchall()
    return {row[0]: row[1] for row in rows}


def update_status(card_id: str, status: str) -> bool:
    if card_id not in INITIAL_STATUSES:
        return False
    conn = _connect()
    conn.execute(
        "UPDATE card_status SET status = ? WHERE card_id = ?",
        (status, card_id),
    )
    conn.commit()
    return True
