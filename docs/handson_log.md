# Databricks ハンズオン実施ログ

実施日: 2026-05-26 〜 2026-05-28  
環境: Databricks Community Edition / Serverless Compute / Unity Catalog有効

---

## 1. Delta Lake

### 概要
ParquetベースのオープンソースストレージフォーマットをDatabricksが拡張したもの。通常のデータレイク（S3等）はUPDATE/DELETEができないが、Delta Lakeはトランザクション管理（ACIDプロパティ）を持つため、UPDATE/DELETE/MERGEが可能。変更履歴をすべて保持するため、過去の任意のバージョンに戻れる（タイムトラベル）。

### 試したこと
- テーブル作成（`demo.people`）
- MERGE（upsert）: Bob更新 + Dave追加
- タイムトラベル: バージョン指定で過去データ参照

### 実行結果

**MERGE後**
```
+---+-------+---+
| id|   name|age|
+---+-------+---+
|  1|  Alice| 30|
|  2|    Bob| 99|  ← 25から更新
|  3|Charlie| 35|
|  4|   Dave| 28|  ← 新規追加
+---+-------+---+
```

**タイムトラベル（version=3）**
```
+---+-------+---+
| id|   name|age|
+---+-------+---+
|  1|  Alice| 30|
|  2|    Bob| 25|  ← MERGE前の値
|  3|Charlie| 35|
+---+-------+---+
```

**DESCRIBE HISTORYで確認できた操作**
| version | operation |
|---------|-----------|
| 0 | CREATE OR REPLACE（初回） |
| 1 | MERGE |
| 2 | OPTIMIZE（自動） |
| 3 | CREATE OR REPLACE（再作成） |
| 4 | MERGE（今回） |
| 5,7 | OPTIMIZE（自動） |

### 気づき
- DatabricksがOPTIMIZEを自動実行してファイルを最適化する（明示的に呼ばなくていい）
- タイムトラベルはversion番号またはtimestampで指定できる

### ユースケース
- 誤ってDELETEしたデータの復元
- ETLパイプラインのデバッグ（どのバージョンで壊れたか特定）
- AthenaではできないUPDATE/DELETE/MERGEが必要な場面

---

## 2. Workflows（ジョブ）

### 概要
NotebookやスクリプトをJobとして登録し、スケジュール実行や依存関係管理ができる機能。AWSのStep FunctionsやGlue Workflowに相当。UIだけで設定でき、実行履歴・ログの確認、複数タスクの順序制御が可能。

### 試したこと
- NotebookをJobとして登録
- Run nowで手動実行

### 実行結果
- Notebookが正常実行され、SELECT結果が出力された

### 気づき
- ジョブ登録はUIのみで完結（コード不要）
- Add triggerでcron式によるスケジュール実行も設定できる

### ユースケース
- 毎日定時にETLを実行
- 複数Notebookを依存関係付きで順番に実行するパイプライン構築

---

## 3. Unity Catalog

### 概要
Databricksのデータガバナンス基盤。カタログ→スキーマ→テーブルの3層構造でデータを管理し、権限管理・Lineage追跡・監査ログを一元提供する。AWSのLake Formationに相当するが、テーブルだけでなくファイル（Volume）やLLMエンドポイント（AI Gateway）も同じ仕組みで管理できる。

### 試したこと
- Catalogエクスプローラーで `workspace.demo.people` を確認
- Sample Data / History / Lineage タブを確認

### 実行結果

**Sample Data**: 4行（Alice/Bob/Charlie/Dave）を表示  
**History**: MERGE・OPTIMIZE・CREATE等の全操作履歴  
**Lineage**: Notebook・Job・Queryが自動記録されていた

Lineageで確認できたアセット:
- `New Notebook 2026-05-26 22:00:00`（Upstream/Downstream）
- `New Job 2026-05-26 22:13:24`（Downstream）
- `New Query 2026-05-14`（Downstream）

### つまずきポイント
- Sample Dataタブで「Sample data is not available without an active SQL warehouse or cluster」と表示された
- → Select computeでSQL Warehouseを選択して解決

### 気づき
- Lineageは手動設定不要。Notebook/Job/Queryを実行するだけで自動記録される
- Historyのリンクから実行したNotebookに直接飛べる

### ユースケース
- データの血統追跡（どのJobが作ったテーブルか）
- 権限管理（SELECT/MODIFY/ALL PRIVILEGESをユーザー/グループ単位で付与）
- コンプライアンス対応（誰がいつデータにアクセスしたか監査）

---

## 4. Auto Loader

### 概要
Volume（S3等）に置かれたファイルを自動検知してDeltaテーブルに取り込むストリーミング取り込み機能。チェックポイントで処理済みファイルを記録するため重複取り込みが起きない。Glue Crawlerの代替として、ファイル到着を監視してBronze層に流し込む用途で使う。

### 試したこと
- Unity Catalog VolumeにCSVを配置
- cloudFilesフォーマットでストリーミング取り込み
- `availableNow=True`でバッチ的に実行

### 実行結果
```
+---+-----+---+-------------+
| id| name|age|_rescued_data|
+---+-----+---+-------------+
| 10|  Eve| 22|         NULL|
| 11|Frank| 33|         NULL|
+---+-----+---+-------------+
```
`_rescued_data`はNULL → スキーマ不一致なし、正常取り込み

### 気づき
- `trigger(availableNow=True)` を指定すると常時起動ではなくバッチ処理として動かせる
- チェックポイントで処理済みを記録するため、同じファイルを2回流しても重複取り込みされない
- `_rescued_data`カラムにスキーマ不一致データが自動格納される（データ損失なし）

### ユースケース
- S3/GCSに届いたファイルをBronze層（Deltaテーブル）に自動取り込み
- Glue Crawlerの代替（設定不要・自動スキーマ検知）
- 実際のDWH: `S3 → Auto Loader → Bronze → Silver → Gold`

---

## 5. SQL Warehouse

### 概要
Spark不要でDeltaテーブルにSQLクエリを投げられる専用の計算エンジン。Notebookを使わずSQL Editorから直接操作でき、Tableau・Power BIからJDBC/ODBCで接続することでBIツールのデータソースとしても使える。アナリスト向けのインターフェース。

### 試したこと
- SQL EditorからUNION ALLクエリを実行
- `workspace.demo.people` と `workspace.demo.autoloader_people` を結合

### 実行結果
```
id=1  Alice    30
id=2  Bob      99
id=3  Charlie  35
id=4  Dave     28
id=10 Eve      22
id=11 Frank    33
```
6行（people 4行 + autoloader_people 2行）が正しく結合された

### つまずきポイント
- SQL EditorにPythonコードを貼り付けてSyntax Errorが出た
- → SQL EditorはSQLのみ。PythonはNotebookで実行

### 気づき
- SQL Warehouseで実行したクエリもUnity CatalogのLineageに自動記録される

### ユースケース
- アナリストがコードなしでDeltaテーブルをクエリ
- Tableau/Power BIからJDBC/ODBCで接続してBIダッシュボードを作成
- Notebookなしで定期SQLレポートを実行

---

## 6. AI Gateway

### 概要
複数のLLM（OpenAI・Anthropic・Gemini・Llama等）へのアクセスをUnity Catalog配下で一元管理するプロキシ機能。各チームが個別にAPIキーを管理する必要がなく、レート制限・使用量追跡・PII検出ガードレールを組織単位で設定できる。Databricksが複数モデルのエンドポイントをデフォルト提供しているため、外部APIキーなしで即使える。

### 試したこと
- AI GatewayのUIで利用可能なエンドポイントを確認
- `mlflow.deployments`経由でLlamaを呼び出し

### 実行結果

利用可能なDatabricks提供エンドポイント（抜粋）:
| エンドポイント | モデル |
|--------------|--------|
| databricks-meta-llama-3-1-8b-instruct | Meta Llama 3.1 |
| databricks-gemini-3-5-flash | Google Gemini |
| databricks-gpt-oss-120b | GPT系OSS |
| databricks-qwen3-next-80b | Alibaba Qwen3 |

Llamaのレスポンス:
> 「Databricks Delta Lakeは、Databricksを用いて構築・管理される高性能ストレージです。データシーケンス管理、データの保存、再利用などを同一のデータストアで実現します。」

### つまずきポイント
- SQL EditorにPythonコードを貼り付けてSyntax Errorが出た（セクション5と同様）
- → Notebookで実行して解決

### 気づき
- Databricksが複数モデルのエンドポイントをデフォルト提供している（外部APIキー不要）
- `endpoint`名を変えるだけで別モデルに切り替えられる
- Unity Catalogと同じガバナンス層で管理される（Lineage・権限・監査ログ）

### ユースケース
- 企業内で複数チームがLLMを使う際の一元管理
- LLM使用量・コストの部門別トラッキング
- PII検出・有害コンテンツのGuardrailsによるブロック
- `Bronze/Silver/Gold層 → AI Gateway → LLM加工` でETLにLLMを組み込む

---

## 全体を通じた気づき

### Databricksの一貫したガバナンス
テーブル・ファイル・LLMすべてをUnity Catalogで一元管理できる。Lake FormationとAI Gatewayを別々に管理するAWS構成より統一感がある。

### Lineageの自動記録
Notebook・Job・SQL Query・AI Gatewayの呼び出しが自動でLineageに記録される。手動でのメタデータ管理が不要。

### Serverlessの恩恵
クラスター起動待ち（数分）がなく、すべてのハンズオンをスムーズに実行できた。
