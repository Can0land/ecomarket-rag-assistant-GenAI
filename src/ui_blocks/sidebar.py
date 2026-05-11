"""Sidebar UI block for the EcoMarket Support Assistant."""

import streamlit as st


def render_sidebar(vectorstore) -> None:
    """Render the EcoMarket sidebar with system info and retrieved sources.

    Args:
        vectorstore: The loaded FAISS vectorstore, or None if unavailable.
    """
    with st.sidebar:
        st.title("🌿 EcoMarket")
        st.subheader("System Info")
        st.markdown(f"**Detected intent:** `{st.session_state.last_intent}`")
        st.markdown(f"**RAG context used:** {'Yes' if st.session_state.rag_used else 'No'}")
        tools_used = any(
            src.get("doc_type") == "agent_tool"
            for src in st.session_state.get("last_sources", [])
        )
        st.markdown(f"**Agent tools used:** {'Yes' if tools_used else 'No'}")
        pending_return = st.session_state.get("pending_return_request")
        if pending_return:
            pending_product = pending_return.get("product_id") or "item pending"
            st.markdown(
                f"**Pending return:** `{pending_return.get('tracking_number')}` / `{pending_product}`"
            )
        if st.session_state.get("blocked_until"):
            st.markdown("**Moderation:** `temporarily paused`")

        if vectorstore is not None:
            st.success("Knowledge base loaded", icon="✅")
        else:
            st.error("Knowledge base not available", icon="❌")

        st.divider()
        st.caption("Powered by Gemma 2B · FAISS · LangChain")

        if st.session_state.last_sources:
            with st.expander("Retrieved sources and agent tools"):
                for src in st.session_state.last_sources:
                    if src.get("doc_type") == "agent_tool":
                        st.markdown(
                            f"- **Tool:** `{src.get('source', '?')}` "
                            f"({src.get('status', 'completed')}) - "
                            f"{src.get('summary', '')}"
                        )
                    else:
                        st.markdown(
                            f"- **{src.get('doc_type', '?')}** "
                            f"(score: {src.get('score', '?')}) - "
                            f"`{src.get('source', '?').split('/')[-1]}`"
                        )
