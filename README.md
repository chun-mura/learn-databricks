# key-services-reference

学習進捗を管理できる「主要サービス・ツール リファレンス」ローカルアプリ。

## セットアップ（初回のみ）

```bash
uv venv
source .venv/bin/activate
uv pip install fastapi uvicorn
```

## 起動

```bash
source .venv/bin/activate
python3 app.py
```

ブラウザで http://localhost:8000 を開く。

## 使い方

カードをクリックするたびにステータスが切り替わる。

| ステータス | 表示 |
|-----------|------|
| 未完了 | バッジなし |
| 進行中 | アンバーバッジ |
| 完了 | グリーンバッジ |

ステータスは `status.db`（SQLite）に保存され、再起動後も維持される。

## ファイル構成

```
app/
├── app.py          # FastAPI サーバー
├── db.py           # SQLite CRUD
├── status.db       # 自動生成（初回起動時）
└── static/
    └── index.html  # フロントエンド
```
# learn-databricks
