import os
import tempfile

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from rag_pipeline import (
    OPENROUTER_MODEL,
    SUPPORTED_FILE_TYPES,
    build_index,
    index_exists,
    load_index,
    process_documents,
    rag_query,
    save_index,
)

st.set_page_config(page_title="Construction RAG Assistant", page_icon=None, layout="wide")


def get_configured_api_key() -> str:
    """Prefer Streamlit secrets or env vars when available."""
    try:
        secret_key = st.secrets.get("OPENROUTER_API_KEY")
        if secret_key:
            return secret_key
    except StreamlitSecretNotFoundError:
        pass

    env_key = os.getenv("OPENROUTER_API_KEY")
    if env_key:
        return env_key

    return ""

st.markdown(
    """
<style>
    .main { background-color: #f5f7fa; }
    .stApp { font-family: 'Segoe UI', sans-serif; }
    .chunk-box {
        background: #fff8e1;
        border-left: 4px solid #f59e0b;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
        font-size: 0.88rem;
        color: #374151;
    }
    .answer-box {
        background: #e8f5e9;
        border-left: 4px solid #22c55e;
        padding: 16px 20px;
        border-radius: 8px;
        font-size: 1rem;
        color: #1a1a2e;
    }
    .meta-tag {
        font-size: 0.75rem;
        color: #6b7280;
        font-weight: 600;
        margin-bottom: 4px;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "index" not in st.session_state:
    st.session_state.index = None
if "chunks" not in st.session_state:
    st.session_state.chunks = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/crane.png", width=70)
    st.title("Setup")
    st.markdown("---")

    configured_api_key = get_configured_api_key()
    if configured_api_key:
        api_key = configured_api_key
        st.success("OpenRouter API key loaded from secrets or environment.")
    else:
        api_key = st.text_input(
            "OpenRouter API Key",
            type="password",
            placeholder="sk-or-...",
            help="Get a free key at https://openrouter.ai",
        )
        if api_key:
            st.success("API key set.")

    st.markdown("---")
    st.markdown(f"**LLM:** `{OPENROUTER_MODEL}`")
    st.markdown("**Embedder:** `all-MiniLM-L6-v2`")
    st.markdown("**Vector DB:** `FAISS (local)`")
    st.markdown("---")

    st.subheader("Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF, DOC, DOCX, or Markdown files",
        type=[ext.lstrip(".") for ext in SUPPORTED_FILE_TYPES],
        accept_multiple_files=True,
        help="Upload PDF, DOC, DOCX, or Markdown files to build the knowledge base.",
    )

    build_btn = st.button("Build Knowledge Base", use_container_width=True, type="primary")

    if index_exists() and st.session_state.index is None:
        if st.button("Load Existing Index", use_container_width=True):
            with st.spinner("Loading saved index..."):
                st.session_state.index, st.session_state.chunks = load_index()
            st.success(f"Loaded {len(st.session_state.chunks)} chunks.")

    if st.session_state.chunks:
        doc_count = len(set(c["source"] for c in st.session_state.chunks))
        st.info(f"**{len(st.session_state.chunks)}** chunks indexed\nfrom **{doc_count}** document(s)")

    st.markdown("---")
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

if build_btn:
    if not uploaded_files:
        st.sidebar.error("Please upload at least one supported document first.")
    else:
        with st.spinner("Processing documents and building index..."):
            tmp_paths = []
            try:
                for uploaded_file in uploaded_files:
                    suffix = os.path.splitext(uploaded_file.name)[1] or ".tmp"
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    try:
                        tmp.write(uploaded_file.read())
                        tmp.flush()
                        tmp_paths.append(tmp.name)
                    finally:
                        tmp.close()

                chunks = process_documents(tmp_paths)
                index = build_index(chunks)
                save_index(index, chunks)

                st.session_state.index = index
                st.session_state.chunks = chunks
            finally:
                for path in tmp_paths:
                    if os.path.exists(path):
                        try:
                            os.unlink(path)
                        except PermissionError:
                            pass

        st.sidebar.success(f"Index built with {len(chunks)} chunks.")
        st.rerun()

st.title("Construction RAG Assistant")
st.caption("Ask questions grounded strictly in your uploaded construction documents.")

if st.session_state.index is None:
    st.warning("Please upload supported documents and click **Build Knowledge Base** to get started.")
elif not api_key:
    st.warning("Please enter your **OpenRouter API Key** in the sidebar.")

for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["query"])
    with st.chat_message("assistant"):
        st.markdown(f'<div class="answer-box">{chat["answer"]}</div>', unsafe_allow_html=True)
        with st.expander(f"Retrieved Context ({len(chat['chunks'])} chunks)"):
            for chunk in chat["chunks"]:
                st.markdown(
                    f'<div class="chunk-box">'
                    f'<div class="meta-tag">{chunk["source"]} | Chunk #{chunk["chunk_id"]} | Rank {chunk["rank"]}</div>'
                    f'{chunk["text"]}'
                    f"</div>",
                    unsafe_allow_html=True,
                )

query = st.chat_input(
    "Ask a question about your documents...",
    disabled=(st.session_state.index is None or not api_key),
)

if query:
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving and generating answer..."):
            try:
                result = rag_query(query, st.session_state.index, st.session_state.chunks, api_key)
                st.markdown(f'<div class="answer-box">{result["answer"]}</div>', unsafe_allow_html=True)
                with st.expander(f"Retrieved Context ({len(result['retrieved_chunks'])} chunks)"):
                    for chunk in result["retrieved_chunks"]:
                        st.markdown(
                            f'<div class="chunk-box">'
                            f'<div class="meta-tag">{chunk["source"]} | Chunk #{chunk["chunk_id"]} | Rank {chunk["rank"]}</div>'
                            f'{chunk["text"]}'
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                st.session_state.chat_history.append(
                    {
                        "query": query,
                        "answer": result["answer"],
                        "chunks": result["retrieved_chunks"],
                    }
                )
            except Exception as e:
                st.error(f"Error: {e}")
