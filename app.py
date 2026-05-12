"""EcoMarket RAG-based Customer Support Assistant.

Streamlit app that combines intent routing, structured data lookup,
and RAG retrieval to generate grounded responses via Gemma 2B.
"""

from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

from src.core.utils import extract_product_id, extract_tracking_number
from src.rag.rag_pipeline import get_vectorstore
from src.ui_blocks.chat_handler import handle_message, _extract_customer_name
from src.ui_blocks.sidebar import render_sidebar

RETURN_LABEL_START = "<!-- RETURN_LABEL_SVG_START -->"
RETURN_LABEL_END = "<!-- RETURN_LABEL_SVG_END -->"
ABUSIVE_BLOCK_DURATION = timedelta(hours=1)
ABUSIVE_BLOCK_MESSAGE = (
    "This chat is temporarily paused because abusive language was used. "
    "Please try again in about 1 hour using respectful language."
)
RETURN_FOLLOWUP_TERMS = {
    "unused",
    "not used",
    "never used",
    "unopened",
    "original condition",
    "original packaging",
    "packaging",
    "intact",
    "labels",
    "accessories",
    "everything is intact",
    "yes",
    "correct",
    "confirm",
}


def render_chat_content(content: str) -> None:
    """Render markdown plus optional SVG return-label artifacts."""
    remaining = content

    while RETURN_LABEL_START in remaining:
        before, rest = remaining.split(RETURN_LABEL_START, 1)
        if before.strip():
            st.markdown(before)

        if RETURN_LABEL_END not in rest:
            st.markdown(rest)
            return

        svg, remaining = rest.split(RETURN_LABEL_END, 1)
        if svg.strip():
            components.html(svg.strip(), height=390, scrolling=False)

    if remaining.strip():
        st.markdown(remaining)


def _looks_like_return_followup(user_input: str) -> bool:
    lowered = user_input.lower()
    return bool(extract_product_id(user_input)) or any(
        term in lowered for term in RETURN_FOLLOWUP_TERMS
    )


def _build_effective_user_input(user_input: str) -> tuple[str, bool]:
    """Attach pending return context to short follow-up confirmations."""
    pending = st.session_state.get("pending_return_request")
    if not pending:
        return user_input, False

    pending_tracking = pending.get("tracking_number")
    if not pending_tracking:
        return user_input, False

    explicit_tracking = extract_tracking_number(user_input)
    if explicit_tracking and explicit_tracking != pending_tracking:
        return user_input, False

    if explicit_tracking and extract_product_id(user_input):
        return user_input, False

    if not _looks_like_return_followup(user_input):
        return user_input, False

    accumulated_input = pending.get("accumulated_input")
    if accumulated_input:
        return f"{accumulated_input} {user_input}", True

    pending_product = pending.get("product_id")
    if pending_product:
        prefix = f"I want to return product {pending_product} from order {pending_tracking}. "
    else:
        prefix = f"I want to return an item from order {pending_tracking}. "

    return prefix + user_input, True


def _update_pending_return_request(
    effective_input: str,
    answer: str,
    sources: list[dict],
    intent: str,
) -> None:
    """Remember return requests that are waiting for user confirmation."""
    if intent != "return_request":
        return

    tool_statuses = [
        src.get("status")
        for src in sources
        if src.get("doc_type") == "agent_tool"
    ]
    tracking = extract_tracking_number(effective_input)
    product_id = extract_product_id(effective_input)

    waiting_for_details = (
        "needs_more_information" in tool_statuses
        or "need to know which item" in answer.lower()
    )

    if waiting_for_details and tracking:
        st.session_state.pending_return_request = {
            "tracking_number": tracking,
            "product_id": product_id,
            "accumulated_input": effective_input,
        }
    else:
        st.session_state.pending_return_request = None


def _is_chat_blocked() -> bool:
    blocked_until = st.session_state.get("blocked_until")
    return bool(blocked_until and datetime.now() < blocked_until)


def _format_blocked_message() -> str:
    blocked_until = st.session_state.get("blocked_until")
    if not blocked_until:
        return ABUSIVE_BLOCK_MESSAGE

    remaining = blocked_until - datetime.now()
    minutes = max(1, int(remaining.total_seconds() // 60))
    return (
        "This chat is temporarily paused because abusive language was used. "
        f"Please try again in about {minutes} minute(s) using respectful language."
    )

# ── page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EcoMarket Support Assistant",
    page_icon="🌿",
    layout="wide",
)

# ── vectorstore initialisation (cached for the session) ───────────────────────


@st.cache_resource(show_spinner="Loading knowledge base…")
def load_vectorstore():
    """Load or build the FAISS vectorstore once per session."""
    try:
        return get_vectorstore()
    except Exception as e:
        st.error(
            f"Could not load the knowledge base: {e}\n\n"
            "Make sure the data files are present in the `data/` folder."
        )
        return None


vectorstore = load_vectorstore()

# ── session state initialisation ─────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_intent" not in st.session_state:
    st.session_state.last_intent = "None"

if "last_sources" not in st.session_state:
    st.session_state.last_sources = []

if "rag_used" not in st.session_state:
    st.session_state.rag_used = False

if "pending_return_request" not in st.session_state:
    st.session_state.pending_return_request = None

if "customer_name" not in st.session_state:
    st.session_state.customer_name = None

if "blocked_until" not in st.session_state:
    st.session_state.blocked_until = None

# ── sidebar ───────────────────────────────────────────────────────────────────

render_sidebar(vectorstore)

# ── page header ───────────────────────────────────────────────────────────────

st.title("Welcome to EcoMarket Support Assistant")
st.caption(
    "Ask me about orders, tracking, shipping, returns, return labels, products, or inventory."
)

# ── render previous messages ──────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        render_chat_content(msg["content"])

# ── chat input ────────────────────────────────────────────────────────────────

user_input = st.chat_input("How can I help you today?")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if _is_chat_blocked():
        answer = _format_blocked_message()
        st.session_state.last_intent = "blocked"
        st.session_state.last_sources = []
        st.session_state.rag_used = False
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            render_chat_content(answer)
        st.rerun()

    effective_input, _continued_return = _build_effective_user_input(user_input)
    detected_name = _extract_customer_name(user_input)
    if detected_name:
        st.session_state.customer_name = detected_name

    with st.spinner("Thinking…"):
        answer, sources, intent, rag_used = handle_message(
            effective_input,
            vectorstore,
            customer_name=st.session_state.customer_name,
        )

    st.session_state.last_intent = intent
    st.session_state.last_sources = sources
    st.session_state.rag_used = rag_used
    _update_pending_return_request(effective_input, answer, sources, intent)
    if intent == "abusive_language":
        st.session_state.blocked_until = datetime.now() + ABUSIVE_BLOCK_DURATION
        st.session_state.pending_return_request = None

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        render_chat_content(answer)

    st.rerun()
