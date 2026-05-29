# 📋 設計書差分チェックツール

設計書（PDF / Excel / Word / PowerPoint / Markdown / テキスト）とローカルのソースコードを比較し、
仕様と実装の差分を自動で検出するツールです。  
**ローカルの DeepSeek モデル（Ollama 経由）** を使用するため、外部 API は一切不要です。

---

## ✅ 主な機能

| 機能 | 説明 |
|------|------|
| 設計書アップロード | PDF, Excel, Word, PowerPoint, Markdown, テキストに対応 |
| ソースコード解析 | ディレクトリを再帰的にスキャン（主要言語すべてに対応） |
| AI 差分チェック | ローカル DeepSeek でバリデーション・ビジネスロジック・バッチ処理などを比較 |
| 結果フィルター | 「問題あり」「要確認」「一致」でフィルタリング＆検索 |
| CSV エクスポート | チェック結果を CSV でダウンロード |

---

## 🛠️ セットアップ手順

### 1. Python のインストール確認

```bash
python3 --version  # 3.10 以上を推奨
```

### 2. Ollama のインストール

[https://ollama.com](https://ollama.com) からダウンロードしてインストールします。

インストール後、Ollama を起動します：

```bash
ollama serve
```

### 3. DeepSeek モデルのダウンロード

お使いのマシンのスペックに合わせてモデルを選択してください：

```bash
# 軽量版（RAM 8GB 以上推奨）
ollama pull deepseek-r1:7b

# 中間版（RAM 16GB 以上推奨）
ollama pull deepseek-r1:14b

# コード特化版
ollama pull deepseek-coder-v2
```

### 4. Python 依存パッケージのインストール

```bash
cd difference-detection-tool

# 仮想環境の作成（推奨）
python3 -m venv .venv
source .venv/bin/activate   # Windows の場合: .venv\Scripts\activate

# パッケージのインストール
pip install -r requirements.txt
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

### Step 2 — ソースコードのパスを指定

- ソースコードのルートディレクトリのフルパスを入力します
- 例：`/Users/yourname/project/my-app`
- 「📁 参照」ボタンでフォルダ選択ダイアログを開くこともできます

### Step 3 — 差分チェックを実行

- 「🔍 差分チェックを開始」ボタンをクリック
- DeepSeek が設計書とソースコードを比較し、結果を表示します
- 処理時間はモデルサイズとコード量によって異なります（数秒〜数分）

### 結果の見方

| ステータス | 意味 |
|-----------|------|
| ✅ 一致    | 設計書の仕様がソースコードに正しく実装されている |
| ⚠️ 問題あり | 明確な差異がある、または未実装の機能がある |
| ℹ️ 要確認  | 部分実装または判断が曖昧で、人による確認が必要 |

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
| DeepSeek モデル | Ollama でインストール済みのモデルを選択 |
| Ollama 接続テスト | Ollama が正常に起動しているか確認 |

---

## 🚨 トラブルシューティング

### Ollama に接続できない

```bash
# Ollama を起動する
ollama serve
```

### モデルが見つからない

```bash
# モデルの一覧を確認
ollama list

# モデルをダウンロード
ollama pull deepseek-r1:7b
```

### PDF が解析できない

```bash
pip install pdfplumber
```

### Word / PowerPoint が解析できない

```bash
pip install python-docx python-pptx
```

### 処理が遅い・タイムアウトする

- より小さいモデル（例：`deepseek-r1:7b`）を使用してください
- ソースコードのディレクトリを絞り込んでください（不要なファイルを除外）

---

## 📦 技術構成

| コンポーネント | 技術 |
|--------------|------|
| UI フレームワーク | Streamlit |
| AI モデル | DeepSeek（Ollama 経由でローカル実行） |
| PDF 解析 | pdfplumber |
| Excel 解析 | openpyxl |
| Word 解析 | python-docx |
| PowerPoint 解析 | python-pptx |
| データ処理 | pandas |

---

## 📁 ファイル構成

```
difference-detection-tool/
├── app.py                        # メイン Streamlit アプリ
├── requirements.txt              # 依存パッケージ
├── README.md                     # このファイル
└── modules/
    ├── __init__.py
    ├── document_parser.py        # 設計書解析（PDF/Excel/Word/PPT/MD/TXT）
    ├── code_reader.py            # ソースコード再帰読み込み
    └── difference_checker.py    # DeepSeek を使った差分検出
```
