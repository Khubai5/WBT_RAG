"""WBT-branded chat with source references inside each answer."""

import base64
import re

import streamlit as st
from groq import APIConnectionError, APIStatusError

from src.answer import answer_question
from src.errors import WBTError
from src.index import MANIFEST_PATH
from src.config import PROJECT_ROOT


LOGO_PATH = PROJECT_ROOT / "assets/wbt-green-icon.png"


STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [data-testid="stApp"] { font-family:Inter,Arial,sans-serif; }
[data-testid="stApp"] { background:linear-gradient(160deg,#103540 0%,#17444f 100%); color:#effcfb; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"] { visibility:hidden; }
.block-container { max-width:880px; padding-top:2rem; padding-bottom:7rem; }
.wbt-brand { display:flex; align-items:center; gap:.85rem; min-width:0; }
.wbt-logo { width:47px; height:47px; object-fit:cover; border-radius:15px; flex:none; }
h1.wbt-title { font-size:1.38rem !important; line-height:1.15 !important; font-weight:700;
    letter-spacing:-.035em; margin:0; padding:0; color:#fff; }
.wbt-subtitle { color:#b9d8d9; font-size:.83rem; margin:.2rem 0 0; }
.wbt-divider { height:1px; background:rgba(216,248,247,.13); margin:1.15rem 0 1.65rem; }
.wbt-label { color:#8fe5e1; font-size:.76rem; font-weight:700; margin:0 0 .35rem; }
.wbt-empty { padding:12vh 0 1rem; color:#d1e8e8; font-size:1.18rem; text-align:center; }
[class*="st-key-chat_"] { border-radius:18px; background:#20515b;
    padding:1.05rem 1.3rem; margin-bottom:.85rem; overflow-wrap:anywhere; }
[class*="st-key-chat_user_"] { background:#285b64; margin-left:10%; }
[class*="st-key-chat_assistant_"] { margin-right:10%; }
[class*="st-key-chat_"] p { color:#f4fcfb; line-height:1.65; }
[data-testid="stButton"] button { border:1px solid rgba(162,221,219,.35); border-radius:999px;
    background:rgba(255,255,255,.08); color:#e9f9f8; font-weight:600;
    min-height:2.45rem; white-space:nowrap; }
[data-testid="stButton"] button:hover { border-color:#54d4d0; color:#fff; background:#285b64; }
.st-key-topbar [data-testid="stButton"] { display:flex; justify-content:flex-end; }
[data-testid="stChatInput"] { max-width:880px; }
[data-testid="stChatInput"] > div { border:1px solid #6cb7b7; border-radius:18px;
    background:#f6fbfa; box-shadow:0 12px 32px rgba(0,0,0,.15); }
[data-testid="stChatInput"] textarea { color:#123b45 !important; }
[data-testid="stChatInput"] textarea::placeholder { color:#607a7e !important; opacity:1; }
a { color:#91ece8; }
@media (max-width:650px) {
    .block-container { padding:1rem .85rem 6rem; }
    .wbt-logo { width:44px; height:44px; border-radius:12px; }
    h1.wbt-title { font-size:1.12rem !important; }
    .wbt-subtitle { font-size:.72rem; }
    [class*="st-key-chat_"] { padding:.9rem 1rem; border-radius:16px; }
    [class*="st-key-chat_user_"] { margin-left:3%; }
    [class*="st-key-chat_assistant_"] { margin-right:3%; }
    [data-testid="stButton"] button { font-size:.76rem; padding:.3rem .65rem; }
    [data-testid="stChatInput"] { width:calc(100% - 1.3rem); }
}
</style>
"""


def answer_with_references(result):
    """Replace model citation numbers with compact, readable source references."""
    sources = {number: meta for number, meta in result.get("sources", [])}

    def reference(match):
        number = int(match.group(1))
        meta = sources.get(number)
        if not meta:
            return match.group(0)
        title = meta["source_title"].replace("[", "\\[").replace("]", "\\]")
        if meta.get("source_type") == "official-webpage":
            return f"[{title}]({meta['url']})"
        return f"[{title}, p. {meta['page_number']}]"

    return re.sub(r"\[(\d+)\]", reference, result["answer"])


def show_history():
    for index, message in enumerate(st.session_state["messages"]):
        label = "You" if message["role"] == "user" else "WBT"
        with st.container(key=f"chat_{message['role']}_{index}"):
            st.markdown(f'<div class="wbt-label">{label}</div>', unsafe_allow_html=True)
            st.markdown(message["content"])


def brand_header():
    logo = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    st.markdown(
        '<div class="wbt-brand">'
        f'<img class="wbt-logo" src="data:image/png;base64,{logo}" alt="WBT logo">'
        '<div><h1 class="wbt-title">We Build Trades</h1>'
        '<p class="wbt-subtitle">Ask about the business</p></div></div>',
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="WBT", layout="centered")
    st.markdown(STYLES, unsafe_allow_html=True)
    st.session_state.setdefault("messages", [])

    with st.container(key="topbar"):
        title, action = st.columns([5, 1.5], vertical_alignment="center", gap="small")
        with title:
            brand_header()
        with action:
            if st.button("New chat"):
                st.session_state["messages"] = []
    st.markdown('<div class="wbt-divider"></div>', unsafe_allow_html=True)

    if not MANIFEST_PATH.is_file():
        st.warning("Search index missing. Run `python -m src.index` in PowerShell.")
    if st.session_state["messages"]:
        show_history()
    else:
        st.markdown('<p class="wbt-empty">What would you like to know?</p>', unsafe_allow_html=True)

    if question := st.chat_input("Ask a question about WBT..."):
        st.session_state["messages"].append({"role": "user", "content": question})
        with st.spinner("Looking through WBT sources..."):
            try:
                result = answer_question(question)
            except APIStatusError as error:
                reply = f"Groq returned HTTP {error.status_code}. Check the key or provider limits."
            except APIConnectionError:
                reply = "Could not connect to Groq. Check the server's network connection and try again."
            except WBTError as error:
                reply = str(error)
            except (OSError, KeyError, TypeError, RuntimeError):
                reply = "The answer could not be completed. Check the terminal for setup details."
            else:
                reply = answer_with_references(result)
        st.session_state["messages"].append({"role": "assistant", "content": reply})
        st.rerun()


if __name__ == "__main__":
    main()
