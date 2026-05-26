# Databricks Getting Started

Community Editionで試したDatabricksの主要機能まとめ。

## 環境

- Databricks Community Edition（無料）
- Serverless Compute（クラスター管理不要）
- Unity Catalog有効

---

## 1. Delta Lake 基本操作

### テーブル作成

```python
spark.sql("CREATE SCHEMA IF NOT EXISTS demo")

data = [
    (1, "Alice", 30),
    (2, "Bob", 25),
    (3, "Charlie", 35),
]
df = spark.createDataFrame(data, ["id", "name", "age"])
df.write.format("delta").mode("overwrite").saveAsTable("demo.people")
```

### MERGE（upsert）

```python
updates = [
    (2, "Bob", 99),   # 既存レコードの更新
    (4, "Dave", 28),  # 新規レコードの追加
]
df_updates = spark.createDataFrame(updates, ["id", "name", "age"])
df_updates.createOrReplaceTempView("updates")

spark.sql("""
    MERGE INTO demo.people AS target
    USING updates AS source
    ON target.id = source.id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")
```

### タイムトラベル

```python
# 変更履歴の確認
spark.sql("DESCRIBE HISTORY demo.people").show(truncate=False)

# バージョン指定で過去のデータを参照
spark.read.format("delta").option("versionAsOf", 0).table("demo.people").show()
```

**ポイント**

- `DESCRIBE HISTORY` で全変更履歴（CREATE/MERGE/OPTIMIZE）を確認できる
- Databricksが自動でOPTIMIZEを実行してファイルを最適化する

---

## 2. Workflows（ジョブ）

Jobs & Pipelines > Create job からNotebookをジョブとして登録・実行できる。

**設定項目**


| 項目        | 設定値             |
| --------- | --------------- |
| Task name | 任意              |
| Type      | Notebook        |
| Source    | Workspace       |
| Path      | 実行するNotebookを選択 |
| Compute   | Serverless      |


**できること**

- Notebookのスケジュール実行（Add trigger）
- 実行履歴・ログの確認
- 複数タスクの依存関係管理

---

## 3. Unity Catalog

カタログ > スキーマ > テーブルの3層構造でデータを管理する。

```
workspace（カタログ）
  └── demo（スキーマ）
        └── people（テーブル）
```

**Catalogエクスプローラーで確認できるタブ**


| タブ          | 内容                      |
| ----------- | ----------------------- |
| Sample Data | データのプレビュー               |
| History     | Delta Lakeの変更履歴         |
| Permissions | アクセス権限の設定（Grant/Revoke） |
| Lineage     | どのNotebook/Jobから作られたか   |
| Insights    | 利用者・アクセス頻度の統計           |


**権限の種類**


| 権限             | 意味                   |
| -------------- | -------------------- |
| SELECT         | 読み取り                 |
| MODIFY         | INSERT/UPDATE/DELETE |
| ALL PRIVILEGES | 全操作                  |


**注意**: DBFSルートはセキュリティ上無効化されている。ファイルストレージにはUnity Catalog Volumeを使う。

---

## 4. Auto Loader

CSVなどのファイルをVolumeに置くだけで自動取り込みできる。

### セットアップ

```python
# Volumeを作成
spark.sql("CREATE VOLUME IF NOT EXISTS workspace.demo.autoloader_input")

# ファイルを配置
volume_path = "/Volumes/workspace/demo/autoloader_input"
dbutils.fs.put(f"{volume_path}/data1.csv",
"""id,name,age
10,Eve,22
11,Frank,33
""", overwrite=True)
```

### Auto Loaderで取り込み

```python
volume_path = "/Volumes/workspace/demo/autoloader_input"

df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("header", "true")
    .option("cloudFiles.schemaLocation", f"{volume_path}/_schema")
    .load(volume_path)
)

(df.writeStream
    .format("delta")
    .option("checkpointLocation", f"{volume_path}/_checkpoint")
    .trigger(availableNow=True)  # 現在あるファイルを処理したら停止
    .toTable("workspace.demo.autoloader_people")
)
```

**ポイント**

- `cloudFiles` フォーマットを指定するだけでファイル到着を自動検知
- チェックポイントで処理済みを記録し、重複取り込みを防ぐ
- `_rescued_data` カラムにスキーマ不一致データが格納される
- 実際のDWHでは `S3 → Auto Loader → Deltaテーブル（Bronze層）` の流れで使う

---

## 5. SQL Warehouse

SQL EditorからDeltaテーブルに直接SQLでクエリできる。

```sql
SELECT * FROM workspace.demo.people
UNION ALL
SELECT id, name, age FROM workspace.demo.autoloader_people
ORDER BY id
```

BIツール（Tableau、Power BIなど）からJDBC/ODBCで接続することもできる。

---

## Glue/Athenaとの比較


| 観点            | Glue + Athena     | Databricks              |
| ------------- | ----------------- | ----------------------- |
| ETLデバッグ       | ジョブ実行しないと確認できない   | Notebookでインタラクティブに確認できる |
| UPDATE/DELETE | Athenaは非対応        | Delta LakeでMERGEまで可能    |
| ファイル取り込み      | Glue Crawlerで手動設定 | Auto Loaderで自動検知        |
| ガバナンス         | Lake Formationで設定 | Unity Catalogで一元管理      |
| コスト           | 使った分だけ（サーバーレス）    | クラスター起動時間課金             |


