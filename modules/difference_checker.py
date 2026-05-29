"""
差分チェックモジュール
Ollama 経由でローカルの DeepSeek モデルを呼び出し、
設計書とソースコードを比較して差分をJSON形式で返します。

DeepSeek R1 系モデルは推論過程を <think>...</think> タグで出力するため、
JSONを取り出す際にタグを除去する処理を含んでいます。
"""

import json
import re
from typing import Generator

# デフォルトモデル（Ollama でプルしたモデル名に合わせて変更してください）
DEFAULT_MODEL = "deepseek-r1:7b"

# DeepSeek へのシステムプロンプト
_SYSTEM_PROMPT = """あなたはシステム設計書とソースコードを比較する専門家です。
設計書の仕様とソースコードの実装を詳細に比較し、差異を検出することが役割です。
必ず日本語で回答してください。必ず指定されたJSON形式のみで回答してください。説明文やマークダウンは不要です。"""

# 比較用プロンプトテンプレート
_COMPARISON_PROMPT = """以下の設計書とソースコードを比較し、差分を検出してください。

## 比較の観点（漏れなく確認すること）
1. 入力項目の必須 / 任意設定とバリデーションルール（文字数、形式、範囲）
2. ビジネスロジック・計算式・計算方法の正確性
3. バッチ処理のタイミング・スケジュール・実行頻度
4. データフロー・処理順序・依存関係
5. エラーハンドリング・例外処理の実装
6. 定数値・閾値・パラメータの一致
7. 業務ルール・制約条件（例：18歳以上、金額の下限・上限など）
8. セキュリティ要件（認証・認可・暗号化など）
9. 業務インパクトの高い差異（データ損失・金額計算ミスなど）
10. その他、設計書に記載された要件の実装状況

## 設計書の内容
{design_doc}

## ソースコードの内容
{source_code}

## 回答形式
以下のJSON形式のみで回答してください。JSON以外のテキストは一切不要です。

{{
  "items": [
    {{
      "item_name": "比較項目名（例：氏名バリデーション、年齢下限チェック）",
      "expected": "設計書に記載されている仕様・期待値",
      "actual": "ソースコードの実装内容（未実装の場合は「未実装」と記載）",
      "status": "一致",
      "details": "差異の詳細説明（一致の場合も簡潔に記載）"
    }}
  ]
}}

status の値:
- "一致"   : 設計書とソースコードが一致している
- "問題あり": 明確な差異がある、または設計書記載の機能が未実装
- "要確認" : 部分的に実装されているが詳細確認が必要、または判断が曖昧

全ての重要な項目を漏れなく列挙してください。"""


_EXTRACT_ITEMS_SYSTEM_PROMPT = """あなたは設計書から仕様項目を抽出する専門家です。
設計書に記載された仕様・ルール・要件を漏れなく抽出し、JSON形式のみで返してください。
必ず日本語で回答してください。"""

_EXTRACT_ITEMS_PROMPT = """以下の設計書から、実装すべき仕様項目をすべて抽出してください。

## 設計書の内容
{design_doc}

## 回答形式
以下のJSON形式のみで回答してください。JSON以外のテキストは不要です。

{{
  "items": [
    {{
      "item_name": "項目名（例：氏名バリデーション）",
      "description": "仕様の詳細（例：必須項目、最大50文字、全角文字のみ）"
    }}
  ]
}}

入力バリデーション、業務ルール、計算ロジック、エラーハンドリング等、
設計書に記載されたすべての仕様項目を網羅的に抽出してください。"""


def extract_items_from_doc(
    design_doc_content: str,
    model: str = DEFAULT_MODEL,
) -> Generator[dict, None, None]:
    """
    設計書から仕様項目をLLMで抽出する。

    Yields:
        {"type": "progress", "content": str}  ストリーミング中の部分テキスト
        {"type": "result",   "data": list}    抽出された項目リスト
        {"type": "error",    "message": str}  エラー発生時のメッセージ
    """
    try:
        import ollama
    except ImportError:
        yield {
            "type": "error",
            "message": "ollama パッケージがインストールされていません。pip install ollama を実行してください。",
        }
        return

    prompt = _EXTRACT_ITEMS_PROMPT.format(design_doc=design_doc_content[:50_000])
    full_response = ""

    try:
        for chunk in ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _EXTRACT_ITEMS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
        ):
            msg = chunk.get("message", {})
            content = msg.get("content", "") or ""
            thinking = msg.get("thinking", "") or ""
            if content:
                full_response += content
            progress_text = thinking or content
            if progress_text:
                yield {"type": "progress", "content": progress_text}

        items = _parse_extracted_items_json(full_response)
        yield {"type": "result", "data": items}

    except Exception as e:
        yield {"type": "error", "message": f"エラーが発生しました: {str(e)}"}


def _parse_extracted_items_json(text: str) -> list[dict]:
    """抽出項目JSONをパースする"""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    code_block = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if code_block:
        json_str = code_block.group(1)
    else:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            return []
        json_str = json_match.group(0)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return []

    return [
        {
            "item_name": str(item.get("item_name", "不明")),
            "description": str(item.get("description", "")),
        }
        for item in data.get("items", [])
    ]


def check_differences(
    design_doc_content: str,
    source_code_content: str,
    model: str = DEFAULT_MODEL,
) -> Generator[dict, None, None]:
    """
    DeepSeek（Ollama経由）で設計書とソースコードの差分をチェックする。

    Yields:
        {"type": "progress", "content": str}  ストリーミング中の部分テキスト
        {"type": "result",   "data": list}    解析完了後の比較結果リスト
        {"type": "error",    "message": str}  エラー発生時のメッセージ
    """
    try:
        import ollama
    except ImportError:
        yield {
            "type": "error",
            "message": "ollama パッケージがインストールされていません。\npip install ollama を実行してください。",
        }
        return

    prompt = _COMPARISON_PROMPT.format(
        # コンテキスト溢れを防ぐため上限を設定
        design_doc=design_doc_content[:50_000],
        source_code=source_code_content[:100_000],
    )

    full_response = ""

    try:
        for chunk in ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
        ):
            msg = chunk.get("message", {})
            content = msg.get("content", "") or ""
            thinking = msg.get("thinking", "") or ""
            if content:
                full_response += content
            progress_text = thinking or content
            if progress_text:
                yield {"type": "progress", "content": progress_text}

        result = _extract_and_parse_json(full_response)
        yield {"type": "result", "data": result}

    except Exception as e:
        error_str = str(e).lower()
        if "model" in error_str and ("not found" in error_str or "pull" in error_str):
            yield {
                "type": "error",
                "message": (
                    f"モデル '{model}' が見つかりません。\n"
                    f"以下のコマンドでダウンロードしてください:\n\n"
                    f"  ollama pull {model}"
                ),
            }
        elif "connection" in error_str or "refused" in error_str or "connect" in error_str:
            yield {
                "type": "error",
                "message": (
                    "Ollama に接続できません。\n"
                    "ターミナルで以下を実行して Ollama を起動してください:\n\n"
                    "  ollama serve"
                ),
            }
        else:
            yield {"type": "error", "message": f"エラーが発生しました: {str(e)}"}


def get_available_models() -> list[str]:
    """Ollama にインストール済みの DeepSeek 系モデル一覧を返す。取得できない場合はデフォルトを返す。"""
    try:
        import ollama

        models_info = ollama.list()
        model_list = getattr(models_info, "models", None) or models_info.get("models", [])
        deepseek_models = [
            (getattr(m, "model", None) or m.get("model", ""))
            for m in model_list
            if "deepseek" in (getattr(m, "model", None) or m.get("model", "")).lower()
        ]
        return deepseek_models if deepseek_models else [DEFAULT_MODEL]
    except Exception:
        return [DEFAULT_MODEL]


# ---- JSON 抽出・正規化ヘルパー ----------------------------------------


def _extract_and_parse_json(text: str) -> list[dict]:
    """
    DeepSeek の出力テキストから JSON を抽出してパースする。
    DeepSeek R1 は <think>...</think> に推論過程を含めるため、まずこれを除去する。
    """
    # 推論ブロックを除去
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # コードブロック内の JSON を優先的に探す（貪欲マッチでネスト全体を取得）
    code_block = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if code_block:
        json_str = code_block.group(1)
    else:
        # コードブロックなしで直接 JSON を探す（最初の { から最後の } まで）
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            return _error_item("JSONの抽出に失敗しました。モデルの出力を確認してください。")
        json_str = json_match.group(0)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # 末尾の余分なテキストを除いて再試行
        brace_depth = 0
        end_pos = 0
        for i, ch in enumerate(json_str):
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    end_pos = i + 1
                    break
        try:
            data = json.loads(json_str[:end_pos])
        except json.JSONDecodeError:
            return _error_item("JSONのパースに失敗しました。モデルの出力形式を確認してください。")

    items = data.get("items", [])
    return [_normalize_item(item) for item in items] if items else _error_item("比較項目が見つかりませんでした。")


def _normalize_item(item: dict) -> dict:
    """比較項目データを正規化して統一的な構造にする"""
    return {
        "item_name": str(item.get("item_name", "不明")),
        "expected": str(item.get("expected", "情報なし")),
        "actual": str(item.get("actual", "情報なし")),
        "status": _normalize_status(str(item.get("status", "要確認"))),
        "details": str(item.get("details", "")),
    }


def _normalize_status(status: str) -> str:
    """ステータス文字列を3種類のいずれかに正規化する"""
    status = status.strip()
    if status in ("一致", "問題あり", "要確認"):
        return status

    low = status.lower()
    if any(k in low for k in ("match", "ok", "正常", "合致")):
        return "一致"
    if any(k in low for k in ("error", "ng", "問題", "missing", "未実装", "mismatch")):
        return "問題あり"
    return "要確認"


def _error_item(message: str) -> list[dict]:
    """エラー発生時のフォールバック結果を生成する"""
    return [
        {
            "item_name": "チェックエラー",
            "expected": "正常に比較結果を取得",
            "actual": message,
            "status": "要確認",
            "details": "設計書とソースコードの内容、およびモデルの出力を確認してください。",
        }
    ]
