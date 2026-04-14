"""Streamlit frontend for SmartBots Bank Reconciliation Agent.

Run:  streamlit run frontend/app.py
"""

import io
import sys
from pathlib import Path

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = "http://127.0.0.1:8001"

st.set_page_config(
    page_title="SmartBots Reconciliation Agent",
    page_icon="🏦",
    layout="wide",
)


def _api(method: str, path: str, **kwargs) -> requests.Response:
    """Helper to call the FastAPI backend."""
    url = f"{API_BASE}{path}"
    return getattr(requests, method)(url, timeout=120, **kwargs)


# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------

pages = [
    "Dashboard",
    "Document Management",
    "Reconciliation",
    "Knowledge Base Search",
]

page = st.sidebar.radio("Navigation", pages)

# ===================================================================
# PAGE: Dashboard
# ===================================================================

if page == "Dashboard":
    st.title("🏦 SmartBots Bank Reconciliation Agent")
    st.markdown("---")

    st.markdown("""
    ### Welcome
    This dashboard provides an interface for:
    - **Document Management** — Upload, browse, and delete documents (PDF, Word, Excel, text)
    - **Reconciliation** — Upload bank/ledger files and run matching
    - **Knowledge Base Search** — Query ingested documents for relevant information

    Select a page from the sidebar to get started.
    """)

    # Quick stats
    st.markdown("### Quick Status")
    col1, col2 = st.columns(2)

    with col1:
        st.metric("API Endpoint", API_BASE)

    with col2:
        try:
            r = _api("get", "/knowledge-base/documents")
            if r.status_code == 200:
                docs = r.json()
                st.metric("Documents in Knowledge Base", len(docs))
            else:
                st.metric("Documents in Knowledge Base", "API error")
        except requests.ConnectionError:
            st.metric("Documents in Knowledge Base", "API offline")


# ===================================================================
# PAGE: Document Management
# ===================================================================

elif page == "Document Management":
    st.title("📄 Document Management")
    st.markdown("Upload documents into the knowledge base or remove existing ones.")
    st.markdown("---")

    # ---------- Upload Section ----------
    st.subheader("Upload Document")
    uploaded = st.file_uploader(
        "Choose a file (PDF, Word, Excel, Text, Markdown, CSV, JSON)",
        type=["pdf", "docx", "xlsx", "xls", "txt", "md", "csv", "json"],
        help="Max 50 MB. The document will be chunked and indexed for retrieval.",
    )

    if uploaded is not None:
        if st.button("Ingest Document", type="primary"):
            with st.spinner("Uploading and processing..."):
                try:
                    files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
                    r = _api("post", "/knowledge-base/upload", files=files)
                    if r.status_code == 200:
                        result = r.json()
                        if result.get("status") == "already_exists":
                            st.warning(f"Document **{result['filename']}** already ingested ({result['chunk_count']} chunks).")
                        elif result.get("status") == "empty_document":
                            st.warning("No text could be extracted from this document.")
                        else:
                            st.success(
                                f"Ingested **{result['filename']}** — "
                                f"{result['chunk_count']} chunks, hash: `{result['content_hash']}`"
                            )
                    else:
                        st.error(f"Upload failed: {r.text}")
                except requests.ConnectionError:
                    st.error("Cannot connect to API. Make sure the backend is running.")

    st.markdown("---")

    # ---------- Documents List ----------
    st.subheader("Ingested Documents")

    if st.button("Refresh List"):
        st.rerun()

    try:
        r = _api("get", "/knowledge-base/documents")
        if r.status_code == 200:
            docs = r.json()
            if not docs:
                st.info("No documents in knowledge base yet.")
            else:
                for doc in docs:
                    with st.expander(f"📄 {doc['filename']}  ({doc['chunk_count']} chunks)"):
                        st.markdown(f"""
                        - **Type:** {doc.get('doc_type', 'N/A')}
                        - **Hash:** `{doc['content_hash']}`
                        - **Chunks:** {doc['chunk_count']}
                        - **Uploaded:** {doc.get('uploaded_at', 'N/A')}
                        """)

                        if st.button(f"Delete {doc['filename']}", key=f"del_{doc['content_hash']}"):
                            dr = _api(
                                "delete",
                                f"/knowledge-base/documents/{doc['filename']}",
                                params={"content_hash": doc["content_hash"]},
                            )
                            if dr.status_code == 200:
                                st.success(f"Deleted {doc['filename']} ({dr.json()['deleted_chunks']} chunks)")
                                st.rerun()
                            else:
                                st.error(f"Delete failed: {dr.text}")
        else:
            st.error(f"Failed to list documents: {r.text}")
    except requests.ConnectionError:
        st.warning("Cannot connect to API. Start the backend with: `uvicorn src.workflow.api:app`")


# ===================================================================
# PAGE: Reconciliation
# ===================================================================

elif page == "Reconciliation":
    st.title("🔄 Reconciliation")
    st.markdown("Upload bank statement and optional ledger file to run reconciliation.")
    st.markdown("---")

    bank_name = st.selectbox("Bank Name", ["Generic", "Chase", "BankOfAmerica"])

    col1, col2 = st.columns(2)
    with col1:
        bank_file = st.file_uploader("Bank Statement (CSV/Excel)", type=["csv", "xlsx", "xls"], key="bank")
    with col2:
        ledger_file = st.file_uploader("Ledger File (optional)", type=["csv", "xlsx", "xls"], key="ledger")

    if bank_file and st.button("Run Reconciliation", type="primary"):
        with st.spinner("Running reconciliation..."):
            try:
                files = {"file": (bank_file.name, bank_file.getvalue(), bank_file.type or "application/octet-stream")}
                data = {"bank_name": bank_name}

                if ledger_file:
                    files["ledger_file"] = (
                        ledger_file.name,
                        ledger_file.getvalue(),
                        ledger_file.type or "application/octet-stream",
                    )

                r = _api("post", "/reconcile", files=files, data=data)
                if r.status_code == 200:
                    run_id = r.json()["run_id"]
                    st.success(f"Reconciliation started. Run ID: `{run_id}`")

                    # Fetch results
                    rr = _api("get", f"/reconcile/{run_id}/report")
                    if rr.status_code == 200:
                        report = rr.json()
                        mc, ul, ub = (
                            report.get("matched_count", 0),
                            report.get("unmatched_ledger_count", 0),
                            report.get("unmatched_bank_count", 0),
                        )

                        c1, c2, c3 = st.columns(3)
                        c1.metric("Matched", mc)
                        c2.metric("Unmatched Ledger", ul)
                        c3.metric("Unmatched Bank", ub)

                        if report.get("matches"):
                            st.subheader("Matched Pairs")
                            st.json(report["matches"][:20])  # show first 20
                    else:
                        st.warning(f"Report not ready: {rr.text}")
                else:
                    st.error(f"Reconciliation failed: {r.text}")
            except requests.ConnectionError:
                st.error("Cannot connect to API.")


# ===================================================================
# PAGE: Knowledge Base Search
# ===================================================================

elif page == "Knowledge Base Search":
    st.title("🔍 Knowledge Base Search")
    st.markdown("Query the document knowledge base for relevant information.")
    st.markdown("---")

    query = st.text_input("Search query", placeholder="e.g. attention mechanism, reconciliation policy...")
    n_results = st.slider("Number of results", 1, 20, 5)

    fname_filter = st.text_input("Filter by filename (optional)", placeholder="e.g. attention-paper.pdf")

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        generate_summary = st.checkbox("Generate AI Summary", value=True, help="Use LLM to synthesize a summary from the retrieved chunks")
    with col_opt2:
        use_reranking = st.checkbox("Enable Reranking", value=False, help="Rerank results using LLM cross-encoder scoring for better relevance")

    if query and st.button("Search", type="primary"):
        with st.spinner("Searching..." if not generate_summary else "Searching & summarizing..."):
            try:
                params = {
                    "q": query,
                    "n": n_results,
                    "summarize": str(generate_summary).lower(),
                    "rerank": str(use_reranking).lower(),
                }
                if fname_filter:
                    params["filename"] = fname_filter

                r = _api("get", "/knowledge-base/search", params=params)
                if r.status_code == 200:
                    data = r.json()
                    chunks = data.get("chunks", [])
                    summary = data.get("summary")

                    if not chunks:
                        st.info("No results found.")
                    else:
                        # Show AI Summary first
                        if summary:
                            st.subheader("📋 AI Summary")
                            st.markdown(summary)
                            st.markdown("---")

                        # Show individual chunks in an expander
                        st.subheader(f"📄 Retrieved Chunks ({len(chunks)})")
                        for i, res in enumerate(chunks, 1):
                            meta = res.get("metadata", {})
                            sim = res.get("similarity", 0)
                            source = meta.get('filename', 'N/A')
                            chunk_label = f"chunk {meta.get('chunk_index', '?')}/{meta.get('total_chunks', '?')}"
                            with st.expander(f"Result {i} — {source} ({chunk_label}) · similarity: {sim:.4f}"):
                                st.text_area(
                                    f"Content",
                                    value=res.get("document", ""),
                                    height=200,
                                    key=f"result_{i}",
                                )
                else:
                    st.error(f"Search failed: {r.text}")
            except requests.ConnectionError:
                st.error("Cannot connect to API.")
