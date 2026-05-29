"""
ソースコードリーダーモジュール
指定されたディレクトリ配下のソースコードを再帰的に収集してテキストとして返します。
一般的なプログラミング言語ファイルおよび設定ファイルに対応します。
"""

from pathlib import Path
from typing import Optional

# 対象とするソースコードの拡張子一覧
SUPPORTED_EXTENSIONS = {
    # プログラミング言語
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rb", ".php",
    ".cs", ".cpp", ".c", ".h", ".hpp",
    ".swift", ".kt", ".rs", ".scala",
    ".vue", ".svelte",
    # Web
    ".html", ".css", ".scss", ".sass", ".less",
    # データ・設定
    ".sql", ".sh", ".bash", ".zsh",
    ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".properties", ".env.example",
    ".json", ".xml",
}

# 解析対象外とするディレクトリ名
EXCLUDED_DIRS = {
    "node_modules", ".git", "__pycache__",
    ".venv", "venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    "vendor", "bower_components",
    ".pytest_cache", ".mypy_cache",
    "coverage", ".tox", "htmlcov",
    ".idea", ".vscode", "target",
}

# 1ファイルあたりの最大サイズ (バイト)
MAX_FILE_SIZE_BYTES = 100 * 1024  # 100 KB

# モデルに渡すコード全体の最大文字数
MAX_TOTAL_CHARS = 150_000


def read_source_code(directory_path: str) -> tuple[str, list[str]]:
    """
    指定ディレクトリ配下のソースコードを再帰的に読み込み、
    結合したコード文字列と読み込んだファイルパスのリストを返す。

    Returns:
        (コード文字列, ファイルパスリスト)
    """
    dir_path = Path(directory_path)

    if not dir_path.exists():
        raise FileNotFoundError(f"ディレクトリが見つかりません: {directory_path}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"指定されたパスはディレクトリではありません: {directory_path}")

    code_files = _collect_code_files(dir_path)

    code_parts: list[str] = []
    file_list: list[str] = []
    total_chars = 0

    for file_path in code_files:
        if total_chars >= MAX_TOTAL_CHARS:
            code_parts.append(
                "\n[注意: 文字数上限に達したため、以降のファイルは省略されました]"
            )
            break

        content = _read_file(file_path)
        if not content:
            continue

        relative = file_path.relative_to(dir_path)
        header = f"\n{'=' * 60}\n// ファイル: {relative}\n{'=' * 60}\n"

        remaining = MAX_TOTAL_CHARS - total_chars
        if len(content) > remaining:
            content = content[:remaining] + "\n[... 文字数上限のため以降を省略 ...]"

        code_parts.append(header + content)
        file_list.append(str(relative))
        total_chars += len(header) + len(content)

    return "\n".join(code_parts), file_list


def get_file_stats(directory_path: str) -> dict:
    """ディレクトリ内のソースコードファイル数と拡張子の内訳を返す"""
    dir_path = Path(directory_path)
    files = _collect_code_files(dir_path)

    extensions: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower()
        extensions[ext] = extensions.get(ext, 0) + 1

    return {"total_files": len(files), "extensions": extensions}


def _collect_code_files(base_dir: Path) -> list[Path]:
    """対象ファイルを再帰収集してパスリストを返す（除外ディレクトリはスキップ）"""
    result: list[Path] = []

    try:
        for item in sorted(base_dir.rglob("*")):
            # 除外ディレクトリ配下はスキップ
            if any(part in EXCLUDED_DIRS for part in item.parts):
                continue
            if not item.is_file():
                continue
            if item.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                if item.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue
            result.append(item)
    except PermissionError:
        pass

    return result


def _read_file(file_path: Path) -> Optional[str]:
    """複数エンコーディングを試みてファイルを読み込む"""
    for encoding in ("utf-8", "utf-8-sig", "shift_jis", "euc-jp", "cp932"):
        try:
            return file_path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return None
