# 📋 設計書差分チェックツール

設計書（PDF / Excel / Word / PowerPoint / Markdown / テキスト）とローカルのソースコードを比較し、
仕様と実装の差分を自動で検出するツールです。  
**Anthropic Claude API** を使用します。

---

## ✅ 主な機能

| 機能 | 説明 |
|------|------|
| 設計書アップロード | PDF, Excel, Word, PowerPoint, Markdown, テキストに対応 |
| 仕様項目の自動抽出 | Claude が設計書から実装すべき仕様項目を抽出・一覧表示 |
| ソースコード解析 | ディレクトリを再帰的にスキャン（主要言語すべてに対応） |
| AI 差分チェック | 抽出済み仕様項目とソースコードを Claude で比較 |
| 重要度評価 | 差分を High / Medium / Low / N/A の4段階で評価 |
| CSV エクスポート | チェック結果を CSV でダウンロード |

---

## 🛠️ セットアップ手順

### 1. Python のインストール確認

```bash
python3 --version  # 3.10 以上を推奨
```

### 2. Anthropic API キーの取得

[Anthropic コンソール](https://console.anthropic.com) で API キーを発行します。

### 3. Python 依存パッケージのインストール

```bash
cd difference-detection-tool

# 仮想環境の作成（推奨）
python3 -m venv .venv
source .venv/bin/activate   # Windows の場合: .venv\Scripts\activate

# パッケージのインストール
pip install -r requirements.txt
```

### 4. API キーの設定（省略可）

起動後にサイドバーから直接入力できますが、以下の方法で事前設定も可能です。

**環境変数で設定する場合：**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**secrets.toml で設定する場合：**
```toml
# .streamlit/secrets.toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

### 5. アプリの起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。

---

## 📖 使い方

### Step 1 — 設計書をアップロード

- 対応形式：**PDF, Excel (.xlsx/.xls), Word (.docx), PowerPoint (.pptx), Markdown (.md), テキスト (.txt)**
- ドラッグ＆ドロップ または「ファイルを選択」ボタンで読み込み
- 「次へ：仕様項目を抽出 →」ボタンを押すと Claude が仕様項目を自動抽出します

### Step 2 — 抽出された仕様項目を確認

- Claude が設計書から抽出した仕様項目の一覧を確認します
- 内容に問題がなければ「確認OK → ソースコードを選択 →」をクリック

### Step 3 — ソースコードのパスを指定

- ソースコードのルートディレクトリのフルパスを入力します
- 例：`/Users/yourname/project/my-app`
- macOS では「📁 参照」ボタンでフォルダ選択ダイアログを開けます

### Step 4 — 差分チェックを実行

- 「🔍 差分チェックを開始」ボタンをクリック
- Claude が抽出済み仕様項目とソースコードを比較し、結果を表示します

### 結果の見方

| ステータス | 意味 |
|-----------|------|
| ✅ 一致    | 設計書の仕様がソースコードに正しく実装されている |
| ⚠️ 問題あり | 明確な差異がある、または未実装の機能がある |
| ℹ️ 要確認  | 部分実装または判断が曖昧で、人による確認が必要 |

### 重要度（Severity）の見方

| 重要度 | 意味 |
|--------|------|
| 🔴 High   | ユーザーが入力・送信・完了できない、必須情報が欠落するなど業務停止レベルの差異 |
| 🟡 Medium | 仕様に関わる品質・堅牢性の問題（業務停止まではしない） |
| 🔵 Low    | 実装細部・コード品質の改善寄りの指摘 |
| － N/A   | 差分なし（「一致」の場合） |

---

## 🔍 差分チェックの観点

以下の観点をもとに AI が差分を検出します：

- **バリデーション**：必須/任意、文字数制限、形式チェック（メール・電話番号など）、範囲チェック
- **ビジネスロジック**：計算式・計算方法・業務ルール・制約条件
- **バッチ処理**：実行タイミング・スケジュール・頻度
- **データフロー**：処理順序・依存関係
- **エラーハンドリング**：例外処理・フォールバック
- **定数・パラメータ**：閾値・設定値の一致
- **セキュリティ要件**：認証・認可・暗号化
- **業務インパクト**：データ損失リスク・金額計算ミスなど重大な差異

---

## ⚙️ 設定

サイドバーから以下を設定できます：

| 設定項目 | 説明 |
|---------|------|
| Anthropic API キー | Anthropic コンソールで発行した API キーを入力 |
| Claude モデル | 使用するモデルを選択 |
| API 接続テスト | API キーが正常に機能しているか確認 |

### 利用可能なモデル

| モデル | 特徴 |
|--------|------|
| **claude-sonnet-4-6**（推奨） | 精度とコストのバランスが最良 |
| **claude-haiku-4-5** | 高速・低コスト |
| **claude-opus-4-8** | 最高精度 |

---

## 🚨 トラブルシューティング

### API キーが無効と表示される

- Anthropic コンソールで発行済みの有効なキーを確認してください
- `sk-ant-` で始まる文字列が正しく入力されているか確認してください

### PDF が解析できない

```bash
pip install pdfplumber
```

### Word / PowerPoint が解析できない

```bash
pip install python-docx python-pptx
```

### 処理が遅い・タイムアウトする

- より高速なモデル（例：`claude-haiku-4-5`）を選択してください
- ソースコードのディレクトリを絞り込んでください（不要なファイルを除外）

---

## 📦 技術構成

| コンポーネント | 技術 |
|--------------|------|
| UI フレームワーク | Streamlit |
| AI モデル | Anthropic Claude API（claude-sonnet-4-6 など） |
| PDF 解析 | pdfplumber |
| Excel 解析 | openpyxl |
| Word 解析 | python-docx |
| PowerPoint 解析 | python-pptx |
| データ処理 | pandas |

---

## 📁 ファイル構成

```
difference-detection-tool/
├── app.py                        # メイン Streamlit アプリ（3画面構成）
├── requirements.txt              # 依存パッケージ
├── README.md                     # このファイル
└── modules/
    ├── __init__.py
    ├── document_parser.py        # 設計書解析（PDF/Excel/Word/PPT/MD/TXT）
    ├── code_reader.py            # ソースコード再帰読み込み
    └── difference_checker.py    # Claude API による仕様抽出・差分検出
```
