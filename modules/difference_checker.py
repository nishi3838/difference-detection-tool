"""
差分チェックモジュール
Anthropic Claude API を呼び出し、
設計書とソースコードを比較して差分をJSON形式で返します。
"""

import json
import re
from typing import Generator

DEFAULT_MODEL = "claude-sonnet-4-6"

AVAILABLE_MODELS = [
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-8",
]

_SYSTEM_PROMPT = """あなたはシステム設計書とソースコードを比較する専門家です。
設計書の仕様とソースコードの実装を詳細に比較し、差異を検出することが役割です。
必ず日本語で回答してください。必ず指定されたJSON形式のみで回答してください。説明文やマークダウンは不要です。"""

_ITEM_BASED_COMPARISON_PROMPT = """以下の設計書から抽出した仕様項目リストについて、ソースコードを確認し、各項目の実装状況を調べてください。

## 確認ルール
各設計書の項目ごとに以下を判断してください：
1. **Code側の状態**: ソースコードに該当する実装があるか → 「あり」または「なし」
2. **差分の内容**:
   - 「あり」の場合：設計書の仕様通りに実装されているか（例: OK / バリデーション不足 / ラベル名が異なるなど）
   - 「なし」の場合：「Codeに未実装」と記載

## 設計書の仕様項目
{extracted_items}

## ソースコードの内容
{source_code}

## 回答形式
以下のJSON形式のみで回答してください。JSON以外のテキストは一切不要です。

{{
  "items": [
    {{
      "item_name": "設計書の項目名",
      "code_status": "あり",
      "difference": "差分の詳細説明（例：OK。ただしラベルが「お名前」になっている）",
      "status": "要確認",
      "severity": "Medium"
    }}
  ]
}}

status の値:
- "一致"   : 設計書とソースコードが完全に一致している
- "問題あり": 未実装、またはバリデーション・ロジックに明確な差異がある
- "要確認" : 実装はあるが細かい差異がある、または詳細確認が必要な場合

severity の値（重要度）:
- "High"   : ユーザーが入力・送信・完了できない、または設計書の必須情報が欠落するもの
             （例：必須フィールドが丸ごと欠如、送信ボタンが動作しない、完了画面へ遷移しない、登録・申込が成立しない）
- "Medium" : 仕様には関係するが業務停止まではしない品質・堅牢性の問題
             （例：生年月日の当日判定のズレ、max属性の欠如、フロントのみ制御でバックエンド検証なし）
- "Low"    : 設計書との差分というより実装細部・コード品質の改善寄りの指摘
             （例：比較条件の微細な差異、型変換の違い、HTML属性の指定不足等）
- "N/A"    : 差分なし（status が「一致」の場合は必ず N/A にすること）

設計書の仕様項目を1件も省略せず、すべて列挙してください。"""


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
    api_key: str | None = None,
) -> Generator[dict, None, None]:
    """
    設計書から仕様項目をLLMで抽出する。

    Yields:
        {"type": "progress", "content": str}  ストリーミング中の部分テキスト
        {"type": "result",   "data": list}    抽出された項目リスト
        {"type": "error",    "message": str}  エラー発生時のメッセージ
    """
    try:
        import anthropic
    except ImportError:
        yield {
            "type": "error",
            "message": "anthropic パッケージがインストールされていません。pip install anthropic を実行してください。",
        }
        return

    if not api_key:
        yield {
            "type": "error",
            "message": "Anthropic API キーが設定されていません。サイドバーで API キーを入力してください。",
        }
        return

    prompt = _EXTRACT_ITEMS_PROMPT.format(design_doc=design_doc_content[:50_000])
    full_response = ""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=_EXTRACT_ITEMS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield {"type": "progress", "content": text}

        items = _parse_extracted_items_json(full_response)
        yield {"type": "result", "data": items}

    except Exception as e:
        error_str = str(e)
        if "authentication" in error_str.lower() or "api_key" in error_str.lower() or "401" in error_str:
            yield {
                "type": "error",
                "message": "API キーが無効です。正しい Anthropic API キーを入力してください。",
            }
        else:
            yield {"type": "error", "message": f"エラーが発生しました: {error_str}"}


def _parse_extracted_items_json(text: str) -> list[dict]:
    """抽出項目JSONをパースする"""
    json_str = _extract_json_object(text)
    if not json_str:
        return []
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
    api_key: str | None = None,
    extracted_items: list[dict] | None = None,
) -> Generator[dict, None, None]:
    """
    Claude API で設計書とソースコードの差分をチェックする。

    Yields:
        {"type": "progress", "content": str}  ストリーミング中の部分テキスト
        {"type": "result",   "data": list}    解析完了後の比較結果リスト
        {"type": "error",    "message": str}  エラー発生時のメッセージ
    """
    try:
        import anthropic
    except ImportError:
        yield {
            "type": "error",
            "message": "anthropic パッケージがインストールされていません。\npip install anthropic を実行してください。",
        }
        return

    if not api_key:
        yield {
            "type": "error",
            "message": "Anthropic API キーが設定されていません。サイドバーで API キーを入力してください。",
        }
        return

    if extracted_items:
        items_text = "\n".join(
            f"- {item['item_name']}: {item.get('description', '')}"
            for item in extracted_items
        )
        prompt = _ITEM_BASED_COMPARISON_PROMPT.format(
            extracted_items=items_text,
            source_code=source_code_content[:100_000],
        )
    else:
        items_text = design_doc_content[:50_000]
        prompt = _ITEM_BASED_COMPARISON_PROMPT.format(
            extracted_items=items_text,
            source_code=source_code_content[:100_000],
        )

    full_response = ""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        with client.messages.stream(
            model=model,
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield {"type": "progress", "content": text}

        result = _extract_and_parse_json(full_response)
        yield {"type": "result", "data": result}

    except Exception as e:
        error_str = str(e)
        if "authentication" in error_str.lower() or "api_key" in error_str.lower() or "401" in error_str:
            yield {
                "type": "error",
                "message": "API キーが無効です。正しい Anthropic API キーを入力してください。",
            }
        else:
            yield {"type": "error", "message": f"エラーが発生しました: {error_str}"}


def get_available_models() -> list[str]:
    """利用可能な Claude モデル一覧を返す。"""
    return AVAILABLE_MODELS


# ---- JSON 抽出・正規化ヘルパー ----------------------------------------


def _extract_json_object(text: str) -> str | None:
    """
    テキストから最初の完全なJSONオブジェクトを抽出する。
    コードブロック（```json ... ```）がある場合はその中を優先して探す。
    波括弧カウントで正確に開始・終了位置を特定するため、
    前後の余分なテキストや入れ子の括弧にも対応できる。
    """
    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    search_text = code_match.group(1).strip() if code_match else text

    start = search_text.find("{")
    if start == -1:
        return None

    depth = 0
    for i, ch in enumerate(search_text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return search_text[start : i + 1]
    return None


def _extract_and_parse_json(text: str) -> list[dict]:
    """Claude の出力テキストから JSON を抽出してパースする。"""
    json_str = _extract_json_object(text)
    if not json_str:
        return _error_item("JSONの抽出に失敗しました。モデルの出力を確認してください。")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return _error_item("JSONのパースに失敗しました。モデルの出力形式を確認してください。")

    items = data.get("items", [])
    return [_normalize_item(item) for item in items] if items else _error_item("比較項目が見つかりませんでした。")


def _normalize_item(item: dict) -> dict:
    """比較項目データを正規化して統一的な構造にする"""
    status = _normalize_status(str(item.get("status", "要確認")))
    return {
        "item_name": str(item.get("item_name", "不明")),
        "code_status": str(item.get("code_status", "不明")),
        "difference": str(item.get("difference", "")),
        "status": status,
        "severity": _normalize_severity(str(item.get("severity", "N/A")), status),
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


def _normalize_severity(severity: str, status: str) -> str:
    """重要度文字列を High / Medium / Low / N/A のいずれかに正規化する"""
    if status == "一致":
        return "N/A"
    s = severity.strip()
    if s in ("High", "Medium", "Low", "N/A"):
        return s
    low = s.lower()
    if "high" in low:
        return "High"
    if "medium" in low:
        return "Medium"
    if "low" in low:
        return "Low"
    return "N/A"


def _error_item(message: str) -> list[dict]:
    """エラー発生時のフォールバック結果を生成する"""
    return [
        {
            "item_name": "チェックエラー",
            "code_status": "不明",
            "difference": message,
            "status": "要確認",
        }
    ]
