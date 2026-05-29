"""
設計書差分チェックツール
設計書（PDF / Excel / Word / PowerPoint / Markdown / テキスト）と
ローカルのソースコードを比較し、差分を自動検出します。
ローカル DeepSeek モデル（Ollama経由）を使用するため、APIキーは不要です。
"""

import streamlit as st
from datetime import datetime
from pathlib import Path
import pandas as pd

from modules.document_parser import parse_document
from modules.code_reader import read_source_code, get_file_stats
from modules.difference_checker import (
    check_differences,
    extract_items_from_doc,
    get_available_models,
    DEFAULT_MODEL,
)

# ────────────────────────────────────────────────────────────
# ページ設定
# ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="設計書差分チェック",
    page_icon="📋",
    layout="wide",
)

# ────────────────────────────────────────────────────────────
# カスタム CSS
# ────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
[data-testid="stAppViewContainer"] { background: #F3F4F6; }
[data-testid="stHeader"] { background: transparent; }

.main .block-container { max-width: 1100px; padding: 2rem 2rem; }

.main-header {
    background: linear-gradient(135deg, #4F46E5 0%, #6D28D9 100%);
    color: white;
    padding: 1.4rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.8rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.main-header h1 { margin: 0; font-size: 1.7rem; }
.main-header p  { margin: 0; opacity: 0.85; font-size: 0.95rem; }

.step-card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.4rem;
}
.step-title {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.6rem;
}
.step-num {
    background: #4F46E5;
    color: white;
    border-radius: 50%;
    width: 30px; height: 30px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.95rem;
    flex-shrink: 0;
}
.step-card h3 { margin: 0; font-size: 1.15rem; }
.step-card p  { color: #6B7280; margin: 0 0 0.8rem 0; font-size: 0.92rem; }

.stat-card {
    border-radius: 12px;
    padding: 1.4rem 1rem;
    text-align: center;
    border: 1px solid;
}
.stat-card .stat-icon  { font-size: 1.8rem; margin-bottom: 0.3rem; }
.stat-card .stat-label { font-size: 0.85rem; color: #6B7280; }
.stat-card .stat-num   { font-size: 2.2rem; font-weight: 800; line-height: 1.1; }
.stat-card .stat-unit  { font-size: 0.8rem;  color: #6B7280; }

.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 6px;
    font-size: 0.82em;
    font-weight: 700;
}
.badge-issue  { background:#FEE2E2; color:#DC2626; }
.badge-review { background:#FEF3C7; color:#D97706; }
.badge-ok     { background:#D1FAE5; color:#059669; }

.tbl-header {
    background: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 8px 8px 0 0;
    padding: 0.65rem 1rem;
    font-weight: 700;
    color: #374151;
    font-size: 0.92rem;
}

.tbl-row {
    background: white;
    border-left: 1px solid #E5E7EB;
    border-right: 1px solid #E5E7EB;
    border-bottom: 1px solid #E5E7EB;
    padding: 0.7rem 1rem;
    font-size: 0.93rem;
}
.tbl-row:hover { background: #F9FAFB; }

div[data-testid="stButton"] button[kind="primary"] {
    background: #4F46E5;
    border: none;
    border-radius: 8px;
    font-weight: 700;
}
div[data-testid="stButton"] button[kind="primary"]:hover {
    background: #4338CA;
}
</style>
""",
    unsafe_allow_html=True,
)

# ────────────────────────────────────────────────────────────
# セッション状態の初期化
# ────────────────────────────────────────────────────────────
_DEFAULTS = {
    "page": "upload",          # upload | review | check
    "results": [],
    "design_doc_name": "",
    "design_doc_content": "",  # 設計書の解析済みテキスト
    "extracted_items": [],     # LLMが抽出した仕様項目
    "source_path": "",
    "file_list": [],
    "selected_model": DEFAULT_MODEL,
}
for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ────────────────────────────────────────────────────────────
# ルーティング
# ────────────────────────────────────────────────────────────

def main():
    if st.session_state.page == "upload":
        _show_upload_page()
    elif st.session_state.page == "review":
        _show_review_page()
    else:
        _show_check_page()


# ════════════════════════════════════════════════════════════
# 共通サイドバー
# ════════════════════════════════════════════════════════════

def _render_sidebar():
    with st.sidebar:
        st.markdown("### ⚙️ 設定")

        available_models = get_available_models()
        selected = st.selectbox(
            "DeepSeek モデル",
            options=available_models,
            index=0,
            help="Ollama でプル済みの DeepSeek モデルを選択してください",
        )
        st.session_state.selected_model = selected

        st.markdown("---")
        if st.button("🔌 Ollama 接続テスト", use_container_width=True):
            try:
                import ollama
                ollama.list()
                st.success("✅ Ollama に接続できました")
            except Exception:
                st.error("❌ Ollama に接続できません\n`ollama serve` を実行してください")

        st.markdown("---")
        st.markdown(
            """
            ### 📖 使い方
            1. 設計書をアップロード
            2. LLMが仕様項目を抽出・確認
            3. ソースコードのパスを入力
            4. 差分チェックを実行

            ### 対応モデル例
            ```
            ollama pull deepseek-r1:7b
            ollama pull deepseek-r1:14b
            ollama pull deepseek-coder-v2
            ```
            """
        )


# ════════════════════════════════════════════════════════════
# ① アップロードページ
# ════════════════════════════════════════════════════════════

def _show_upload_page():
    st.markdown(
        """
        <div class="main-header">
            <span style="font-size:2.2rem">📋</span>
            <div>
                <h1>設計書差分チェック</h1>
                <p>設計書とソースコードの差分を自動でチェックします</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_sidebar()

    st.markdown(
        """
        <div class="step-card">
          <div class="step-title">
            <div class="step-num">1</div>
            <h3>設計書をUpload</h3>
          </div>
          <p>設計書ファイルをドラッグ＆ドロップするか、下のボタンから選択してください。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "設計書ファイルを選択",
        type=["pdf", "xlsx", "xls", "docx", "pptx", "md", "txt"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        size_kb = uploaded_file.size / 1024
        st.success(f"✅ **{uploaded_file.name}**  ({size_kb:.1f} KB) を選択しました")

    st.caption(
        "対応ファイル形式：PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx),"
        " Markdown (.md), テキスト (.txt)"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(
        "次へ：仕様項目を抽出 →",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_file,
    ):
        _run_extract(uploaded_file)


def _run_extract(uploaded_file):
    """設計書をパース → LLMで仕様項目を抽出してレビューページへ遷移する"""
    status_msg = st.empty()
    progress_box = st.empty()

    try:
        status_msg.info("📄 設計書を解析中...")
        design_content = parse_document(uploaded_file)
        if not design_content.strip():
            st.error("設計書の内容を抽出できませんでした。ファイル形式と内容を確認してください。")
            return

        model = st.session_state.selected_model
        status_msg.info(f"🤖 DeepSeek ({model}) で仕様項目を抽出中...  しばらくお待ちください。")

        response_text = ""
        items = None

        for chunk in extract_items_from_doc(design_content, model=model):
            if chunk["type"] == "progress":
                response_text += chunk["content"]
                display = response_text[-600:] if len(response_text) > 600 else response_text
                progress_box.code(display, language=None)
            elif chunk["type"] == "result":
                items = chunk["data"]
                progress_box.empty()
                status_msg.empty()
            elif chunk["type"] == "error":
                progress_box.empty()
                status_msg.empty()
                st.error(f"❌ {chunk['message']}")
                return

        if items is not None:
            st.session_state.design_doc_content = design_content
            st.session_state.design_doc_name = uploaded_file.name
            st.session_state.extracted_items = items
            st.session_state.page = "review"
            st.rerun()
        else:
            st.error("仕様項目の抽出に失敗しました。")

    except Exception as e:
        st.error(f"❌ 予期しないエラーが発生しました: {e}")


# ════════════════════════════════════════════════════════════
# ② レビューページ（抽出項目の確認）
# ════════════════════════════════════════════════════════════

def _show_review_page():
    st.markdown(
        """
        <div class="main-header">
            <span style="font-size:2.2rem">📋</span>
            <div>
                <h1>設計書差分チェック</h1>
                <p>設計書とソースコードの差分を自動でチェックします</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_sidebar()

    if st.button("← 戻る（設計書を変更）"):
        st.session_state.page = "upload"
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="step-card">
          <div class="step-title">
            <div class="step-num">2</div>
            <h3>抽出された仕様項目を確認</h3>
          </div>
          <p>設計書から以下の仕様項目が抽出されました。内容を確認してください。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    items = st.session_state.extracted_items
    doc_name = st.session_state.design_doc_name

    st.caption(f"設計書: **{doc_name}**")

    if not items:
        st.warning("仕様項目が抽出できませんでした。設計書の内容を確認してください。")
    else:
        st.info(f"**{len(items)} 件** の仕様項目が抽出されました。")

        df = pd.DataFrame(items).rename(
            columns={"item_name": "項目名", "description": "仕様内容"}
        )
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(
        "✅ 確認OK → ソースコードを選択 →",
        type="primary",
        use_container_width=True,
        disabled=not items,
    ):
        st.session_state.page = "check"
        st.rerun()


# ════════════════════════════════════════════════════════════
# ③④ コード選択 → 差分検証ページ
# ════════════════════════════════════════════════════════════

def _show_check_page():
    st.markdown(
        """
        <div class="main-header">
            <span style="font-size:2.2rem">📋</span>
            <div>
                <h1>設計書差分チェック</h1>
                <p>設計書とソースコードの差分を自動でチェックします</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_sidebar()

    if st.button("← 戻る（項目を確認）"):
        st.session_state.page = "review"
        st.session_state.results = []
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 3: ソースコードのパスを選択 ────────────────────
    st.markdown(
        """
        <div class="step-card">
          <div class="step-title">
            <div class="step-num">3</div>
            <h3>SourceCodeを選択</h3>
          </div>
          <p>ローカルのソースコードディレクトリのパスを指定してください。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_input, col_btn = st.columns([6, 1])

    with col_input:
        source_path = st.text_input(
            "ソースコードパス",
            value=st.session_state.source_path,
            placeholder="例）/Users/yourname/project/my-source-code",
            label_visibility="collapsed",
        )
        st.session_state.source_path = source_path

    with col_btn:
        if st.button("📁 参照", use_container_width=True):
            _open_folder_dialog()

    if source_path:
        p = Path(source_path)
        if p.exists() and p.is_dir():
            try:
                stats = get_file_stats(source_path)
                ext_summary = ", ".join(
                    f"{ext}({n})" for ext, n in sorted(stats["extensions"].items())
                )
                st.success(
                    f"✅ **{stats['total_files']}** 個のファイルを検出しました  "
                    f"（{ext_summary}）"
                )
            except Exception as e:
                st.error(f"エラー: {e}")
        else:
            st.warning("⚠️ 指定されたディレクトリが見つかりません")
    else:
        st.caption("ソースコードのルートディレクトリのパスを入力してください。")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 4: 差分チェックボタン ───────────────────────────
    st.markdown(
        """
        <div class="step-card">
          <div class="step-title">
            <div class="step-num">4</div>
            <h3>差分を検証</h3>
          </div>
          <p>ソースコードと抽出済み仕様項目を比較して差分を検出します。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    can_check = bool(source_path and Path(source_path).is_dir())

    if st.button(
        "🔍 差分チェックを開始",
        type="primary",
        use_container_width=True,
        disabled=not can_check,
    ):
        _run_check(source_path)

    if not can_check and source_path:
        st.info("💡 有効なソースコードディレクトリのパスを入力してください")

    if st.session_state.results:
        _show_results_inline()


def _open_folder_dialog():
    """macOS の osascript でフォルダ選択ダイアログを開く"""
    try:
        import subprocess

        result = subprocess.run(
            ["osascript", "-e", 'tell app "Finder" to POSIX path of (choose folder with prompt "ソースコードのフォルダを選択")'],
            capture_output=True,
            text=True,
            timeout=60,
        )
        folder = result.stdout.strip().rstrip("/")
        if folder:
            st.session_state.source_path = folder
            st.rerun()
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        st.warning("フォルダ選択ダイアログを開けませんでした。直接パスを入力してください。")


def _run_check(source_path: str):
    """ソースコード読み込み → DeepSeek による差分検出を実行する"""
    design_content = st.session_state.design_doc_content
    status_msg = st.empty()
    progress_box = st.empty()

    try:
        status_msg.info("💻 ソースコードを読み込み中...")
        source_content, file_list = read_source_code(source_path)
        if not source_content.strip():
            st.error("ソースコードを読み込めませんでした。ディレクトリとファイルを確認してください。")
            return

        model = st.session_state.selected_model
        status_msg.info(
            f"🤖 DeepSeek ({model}) で差分を分析中..."
            f"  — {len(file_list)} 個のファイルを検査します。しばらくお待ちください。"
        )

        response_text = ""
        results = None

        for chunk in check_differences(design_content, source_content, model=model):
            if chunk["type"] == "progress":
                response_text += chunk["content"]
                display = response_text[-600:] if len(response_text) > 600 else response_text
                progress_box.code(display, language=None)
            elif chunk["type"] == "result":
                results = chunk["data"]
                progress_box.empty()
                status_msg.empty()
            elif chunk["type"] == "error":
                progress_box.empty()
                status_msg.empty()
                st.error(f"❌ {chunk['message']}")
                return

        if results:
            st.session_state.results = results
            st.session_state.file_list = file_list
            st.rerun()
        else:
            st.error("差分チェック結果を取得できませんでした。")

    except FileNotFoundError as e:
        st.error(f"❌ {e}")
    except Exception as e:
        st.error(f"❌ 予期しないエラーが発生しました: {e}")


def _show_results_inline():
    """差分チェック結果をチェックページ内に直接表示する"""
    results = st.session_state.results

    st.markdown("---")
    st.subheader("差分チェック結果")

    total = len(results)
    issue_n = sum(1 for r in results if r["status"] == "問題あり")
    review_n = sum(1 for r in results if r["status"] == "要確認")
    ok_n = sum(1 for r in results if r["status"] == "一致")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("チェック対象", total)
    c2.metric("問題あり", issue_n)
    c3.metric("要確認", review_n)
    c4.metric("一致", ok_n)

    st.markdown("<br>", unsafe_allow_html=True)

    df = pd.DataFrame(results).rename(
        columns={
            "item_name": "項目名",
            "expected": "設計書（期待）",
            "actual": "アプリ（実装）",
            "status": "結果",
            "details": "詳細",
        }
    )

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ 結果をCSVでダウンロード",
        data=csv,
        file_name=f"差分チェック結果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )


# ════════════════════════════════════════════════════════════
# 結果ページ（旧実装・参照用として保持）
# ════════════════════════════════════════════════════════════

PAGE_SIZE = 6


def _show_results_page():
    results: list[dict] = st.session_state.results

    nav_col, title_col, dl_col = st.columns([2, 5, 2])

    with nav_col:
        if st.button("← 前の画面に戻る"):
            st.session_state.page = "check"
            st.rerun()

    with title_col:
        st.markdown(
            """
            <div style="text-align:center; padding-top:0.3rem;">
              <h2 style="margin:0; color:#111827;">✅ 差分チェック結果</h2>
              <p style="color:#6B7280; margin:0; font-size:0.9rem;">設計書とアプリの実装を比較した結果です</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with dl_col:
        df = pd.DataFrame(results).rename(
            columns={
                "item_name": "項目名",
                "expected": "設計書（期待）",
                "actual": "アプリ（実装）",
                "status": "結果",
                "details": "詳細",
            }
        )
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ 結果をダウンロード",
            data=csv,
            file_name=f"差分チェック結果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    total = len(results)
    issue_n = sum(1 for r in results if r["status"] == "問題あり")
    review_n = sum(1 for r in results if r["status"] == "要確認")
    ok_n = sum(1 for r in results if r["status"] == "一致")

    c1, c2, c3, c4 = st.columns(4)
    _stat_card(c1, "📋", "#EFF6FF", "#DBEAFE", "#1E40AF", "チェック対象", total)
    _stat_card(c2, "⚠️", "#FFF5F5", "#FED7D7", "#DC2626", "問題あり", issue_n)
    _stat_card(c3, "ℹ️", "#FFFBEB", "#FDE68A", "#D97706", "要確認", review_n)
    _stat_card(c4, "✅", "#F0FDF4", "#BBF7D0", "#059669", "一致", ok_n)

    st.markdown("<br>", unsafe_allow_html=True)

    filter_col, search_col = st.columns([3, 2])

    with filter_col:
        tab_labels = {
            "すべて": total,
            "問題あり": issue_n,
            "要確認": review_n,
            "一致": ok_n,
        }
        btn_cols = st.columns(4)
        for i, (label, count) in enumerate(tab_labels.items()):
            with btn_cols[i]:
                is_active = st.session_state.current_filter == label
                if st.button(
                    f"{label} ({count})",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                    key=f"tab_{label}",
                ):
                    st.session_state.current_filter = label
                    st.session_state.current_page = 1
                    st.rerun()

    with search_col:
        query = st.text_input(
            "検索",
            value=st.session_state.search_query,
            placeholder="🔍 項目名で検索...",
            label_visibility="collapsed",
            key="search_box",
        )
        if query != st.session_state.search_query:
            st.session_state.search_query = query
            st.session_state.current_page = 1

    st.markdown("<br>", unsafe_allow_html=True)

    filtered = results
    if st.session_state.current_filter != "すべて":
        filtered = [r for r in filtered if r["status"] == st.session_state.current_filter]
    if st.session_state.search_query:
        q = st.session_state.search_query.lower()
        filtered = [r for r in filtered if q in r["item_name"].lower()]

    if not filtered:
        st.info("条件に一致する項目がありません。")
    else:
        total_items = len(filtered)
        total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
        cur_page = min(st.session_state.current_page, total_pages)
        start = (cur_page - 1) * PAGE_SIZE
        end = min(start + PAGE_SIZE, total_items)
        page_items = filtered[start:end]

        st.markdown(
            """
            <div class="tbl-header">
              <div style="display:grid; grid-template-columns:2.2fr 2fr 2fr 1.5fr 0.3fr; gap:0.5rem;">
                <span>項目名</span>
                <span>設計書（期待）</span>
                <span>アプリ（実装）</span>
                <span>結果</span>
                <span></span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for idx, item in enumerate(page_items):
            _render_row(item, f"row_{start + idx}")

        st.markdown(
            f"<p style='color:#6B7280; font-size:0.88rem; margin-top:0.6rem;'>"
            f"{start + 1}–{end} / {total_items} 件</p>",
            unsafe_allow_html=True,
        )

        if total_pages > 1:
            _render_pagination(cur_page, total_pages)


def _stat_card(col, icon, bg, border, text_color, label, value):
    col.markdown(
        f"""
        <div style="background:{bg}; border:1px solid {border}; border-radius:12px;
                    padding:1.2rem 0.5rem; text-align:center;">
          <div style="font-size:1.7rem">{icon}</div>
          <div style="font-size:0.82rem; color:#6B7280">{label}</div>
          <div style="font-size:2rem; font-weight:800; color:{text_color}">{value}</div>
          <div style="font-size:0.78rem; color:#6B7280">項目</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _badge_html(status: str) -> str:
    configs = {
        "問題あり": ("⚠️ 問題あり", "badge-issue"),
        "要確認": ("ℹ️ 要確認", "badge-review"),
        "一致": ("✅ 一致", "badge-ok"),
    }
    label, cls = configs.get(status, ("❓ 不明", "badge-review"))
    return f'<span class="badge {cls}">{label}</span>'


def _actual_color(status: str) -> str:
    return {"問題あり": "#DC2626", "要確認": "#D97706", "一致": "#059669"}.get(status, "#374151")


def _render_row(item: dict, key: str):
    status = item["status"]

    st.markdown(
        f"""
        <div class="tbl-row">
          <div style="display:grid; grid-template-columns:2.2fr 2fr 2fr 1.5fr 0.3fr; gap:0.5rem; align-items:center;">
            <span style="font-weight:600">{item['item_name']}</span>
            <span style="color:#374151">{item['expected']}</span>
            <span style="color:{_actual_color(status)}">{item['actual']}</span>
            <span>{_badge_html(status)}</span>
            <span></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if item.get("details"):
        with st.expander("📝 詳細を表示", expanded=False):
            st.markdown(
                f"<div style='background:#F9FAFB; border-radius:8px; padding:0.8rem 1rem; color:#374151;'>"
                f"{item['details']}"
                f"</div>",
                unsafe_allow_html=True,
            )


def _render_pagination(current_page: int, total_pages: int):
    cols = st.columns([1, 0.5, 0.5, 0.5, 0.5, 0.5, 1])

    with cols[1]:
        if current_page > 1 and st.button("‹", key="pg_prev"):
            st.session_state.current_page = current_page - 1
            st.rerun()

    start_p = max(1, current_page - 1)
    end_p = min(total_pages + 1, start_p + 3)
    for i, col_slot in enumerate(cols[2:5]):
        pg = start_p + i
        if pg >= end_p:
            break
        with col_slot:
            if st.button(
                str(pg),
                type="primary" if pg == current_page else "secondary",
                key=f"pg_{pg}",
            ):
                st.session_state.current_page = pg
                st.rerun()

    with cols[5]:
        if current_page < total_pages and st.button("›", key="pg_next"):
            st.session_state.current_page = current_page + 1
            st.rerun()


# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
