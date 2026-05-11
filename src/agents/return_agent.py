"""Return automation agent for EcoMarket customer support."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool

from src.agents.return_tools import build_return_tools
from src.core.utils import extract_product_id, extract_tracking_number
from src.llm.llm_client import generate_llm_response
from src.services.order_service import get_order


@dataclass
class ReturnAgentResult:
    """Result returned by the return automation agent."""

    answer: str
    status: str
    trace: list[dict[str, Any]]


def _clean_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    """Best-effort JSON object extraction from an LLM response."""
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _interpret_context_with_llm(user_input: str) -> dict[str, Any]:
    """Use the local LLM as a narrow semantic parser for return confirmations."""
    prompt = f"""
You classify short customer messages for an EcoMarket return request.

Return ONLY a valid JSON object with these keys:
{{
  "return_reason": "damaged|defective|incorrect_item|spoiled|expired_on_arrival|change_of_mind|unspecified",
  "unused": true/false/null,
  "packaging_intact": true/false/null,
  "photo_evidence": true/false/null,
  "reported_within_48h": true/false/null
}}

Rules:
- Interpret semantic variations, not only exact words.
- "all is intact", "everything is intact", "the item is intact", "box is okay",
  "packaging looks fine", or "nothing is missing" imply packaging_intact=true.
- "unused", "not used", "never used", "still new", or "original condition" imply unused=true.
- Do not infer unused=true from "intact" alone.
- Photo evidence is true only if the customer says they uploaded, attached, or have photos/pictures.
- If a field is unknown, use null.

Customer message:
{user_input}
""".strip()

    response = generate_llm_response(prompt, max_tokens=180)
    return _extract_json_object(response)


def _merge_llm_context(base: dict[str, Any], llm_context: dict[str, Any]) -> dict[str, Any]:
    """Merge LLM-parsed confirmations without overriding deterministic signals."""
    allowed_reasons = {
        "damaged",
        "defective",
        "incorrect_item",
        "spoiled",
        "expired_on_arrival",
        "change_of_mind",
        "unspecified",
    }

    merged = dict(base)
    reason = llm_context.get("return_reason")
    if merged.get("return_reason") == "unspecified" and reason in allowed_reasons:
        merged["return_reason"] = reason

    for key in ("unused", "packaging_intact", "photo_evidence", "reported_within_48h"):
        value = llm_context.get(key)
        if merged.get(key) is None and isinstance(value, bool):
            merged[key] = value

    return merged


def _extract_request_context(user_input: str) -> dict[str, Any]:
    lowered = user_input.lower()

    reason = "unspecified"
    if any(word in lowered for word in ("wrong", "incorrect")):
        reason = "incorrect_item"
    elif any(word in lowered for word in ("damaged", "damage", "broken")):
        reason = "damaged"
    elif "defect" in lowered:
        reason = "defective"
    elif any(word in lowered for word in ("spoiled", "spoilt")):
        reason = "spoiled"
    elif "expired" in lowered or "expiration" in lowered:
        reason = "expired_on_arrival"
    elif any(phrase in lowered for phrase in ("changed my mind", "no longer need", "do not want", "don't want")):
        reason = "change_of_mind"

    unused = None
    positive_unused = any(
        word in lowered
        for word in (
            "unused",
            "unopened",
            "not used",
            "never used",
            "original condition",
            "still new",
            "brand new",
        )
    )
    negative_used = any(word in lowered for word in ("used", "washed"))
    if positive_unused:
        unused = True
    elif negative_used:
        unused = False
    if "opened" in lowered and "unopened" not in lowered:
        unused = False

    packaging_intact = None
    if any(
        phrase in lowered
        for phrase in (
            "packaging intact",
            "original packaging",
            "labels intact",
            "accessories intact",
            "everything is intact",
            "all is intact",
            "all intact",
            "it is intact",
            "item is intact",
            "the item is intact",
            "box is fine",
            "box is okay",
            "box is ok",
            "packaging is fine",
            "packaging is okay",
            "packaging is ok",
            "nothing is missing",
        )
    ):
        packaging_intact = True
    if any(phrase in lowered for phrase in ("no packaging", "without packaging", "packaging is damaged", "missing label")):
        packaging_intact = False

    photo_evidence = None
    if any(word in lowered for word in ("photo", "photos", "picture", "evidence", "uploaded")):
        photo_evidence = True

    reported_within_48h = None
    if any(phrase in lowered for phrase in ("within 48 hours", "same day", "today", "yesterday")):
        reported_within_48h = True
    if any(phrase in lowered for phrase in ("after 48 hours", "three days later", "3 days later", "last week")):
        reported_within_48h = False

    context = {
        "return_reason": reason,
        "unused": unused,
        "packaging_intact": packaging_intact,
        "photo_evidence": photo_evidence,
        "reported_within_48h": reported_within_48h,
    }
    semantic_terms = (
        "intact",
        "fine",
        "okay",
        " ok",
        "good condition",
        "still new",
        "sealed",
        "complete",
        "nothing missing",
        "photo",
        "picture",
        "uploaded",
        "attached",
        "today",
        "yesterday",
        "same day",
        "within 48",
    )
    missing_core_confirmation = unused is None or packaging_intact is None
    possible_photo_claim = reason in {
        "damaged",
        "defective",
        "incorrect_item",
        "spoiled",
        "expired_on_arrival",
    } and (photo_evidence is None or reported_within_48h is None)
    should_use_llm = (missing_core_confirmation or possible_photo_claim) and any(
        term in lowered for term in semantic_terms
    )
    if not should_use_llm:
        return context

    llm_context = _interpret_context_with_llm(user_input)
    return _merge_llm_context(context, llm_context)


def _find_product_in_order(order: dict[str, Any], user_input: str) -> dict[str, Any] | None:
    product_id = extract_product_id(user_input)
    if product_id:
        for item in order.get("items", []):
            if item.get("product_id", "").upper() == product_id:
                return item

    lowered = _clean_token(user_input)
    for item in order.get("items", []):
        name = _clean_token(item.get("product_name", ""))
        if name and name in lowered:
            return item

    content_words = set(lowered.split())
    best_item = None
    best_overlap = 0
    for item in order.get("items", []):
        name_words = {
            word
            for word in _clean_token(item.get("product_name", "")).split()
            if len(word) > 2
        }
        overlap = len(name_words & content_words)
        if overlap > best_overlap:
            best_item = item
            best_overlap = overlap

    if best_overlap >= 2:
        return best_item
    if len(order.get("items", [])) == 1:
        return order["items"][0]
    return None


def _format_item_options(order: dict[str, Any]) -> str:
    return "\n".join(
        f"- **{item.get('product_id')}**: {item.get('product_name')} x{item.get('quantity')}"
        for item in order.get("items", [])
    )


class ReturnAutomationAgent:
    """Deterministic LangChain-tool agent for EcoMarket return requests."""

    def __init__(self, tools: list[StructuredTool] | None = None) -> None:
        self.tools = {tool.name: tool for tool in (tools or build_return_tools())}

    def _invoke_tool(self, name: str, payload: dict[str, Any], trace: list[dict[str, Any]]) -> Any:
        result = self.tools[name].invoke(payload)
        trace.append(
            {
                "tool": name,
                "status": result.get("status", "completed") if isinstance(result, dict) else "completed",
                "summary": self._summarize_tool_result(result),
            }
        )
        return result

    @staticmethod
    def _summarize_tool_result(result: Any) -> str:
        if not isinstance(result, dict):
            return str(result)
        if result.get("missing_information"):
            return "Missing: " + ", ".join(result["missing_information"])
        if result.get("reasons"):
            return "; ".join(result["reasons"][:2])
        if result.get("label_id"):
            return f"Generated label {result['label_id']}"
        return result.get("status", "completed")

    def run(self, user_input: str, policy_context: str = "") -> ReturnAgentResult:
        trace: list[dict[str, Any]] = []
        tracking_number = extract_tracking_number(user_input)

        if not tracking_number:
            return ReturnAgentResult(
                answer=(
                    "I can help start a return. Please send the order tracking number "
                    "(for example **ECO20106**) and the product you want to return."
                ),
                status="needs_more_information",
                trace=trace,
            )

        order = get_order(tracking_number)
        if not order:
            return ReturnAgentResult(
                answer=(
                    f"I could not find order **{tracking_number}** in EcoMarket records. "
                    "Please double-check the tracking number before I start a return."
                ),
                status="error",
                trace=trace,
            )

        item = _find_product_in_order(order, user_input)
        if not item:
            return ReturnAgentResult(
                answer=(
                    f"I found order **{tracking_number}**, but I need to know which item you want to return.\n\n"
                    f"Items in this order:\n{_format_item_options(order)}"
                ),
                status="needs_more_information",
                trace=trace,
            )

        context = _extract_request_context(user_input)
        verification = self._invoke_tool(
            "verify_return_eligibility",
            {
                "tracking_number": tracking_number,
                "product_id": item["product_id"],
                **context,
            },
            trace,
        )

        if verification.get("status") == "eligible":
            label = self._invoke_tool(
                "generate_return_label",
                {
                    "tracking_number": tracking_number,
                    "product_id": item["product_id"],
                    "shipping_cost_responsibility": verification.get(
                        "shipping_cost_responsibility", "customer"
                    ),
                },
                trace,
            )
            log_label = {k: v for k, v in label.items() if k != "label_svg"}
            self._invoke_tool(
                "log_return_action",
                {
                    "action": "return_label_generated",
                    "tracking_number": tracking_number,
                    "product_id": item["product_id"],
                    "status": "approved",
                    "details_json": json.dumps(
                        {"verification": verification, "label": log_label},
                        ensure_ascii=False,
                    ),
                },
                trace,
            )
            return ReturnAgentResult(
                answer=self._format_success_answer(item, verification, label),
                status="approved",
                trace=trace,
            )

        if verification.get("status") == "manual_review":
            self._invoke_tool(
                "log_return_action",
                {
                    "action": "return_manual_review_required",
                    "tracking_number": tracking_number,
                    "product_id": item["product_id"],
                    "status": "manual_review",
                    "details_json": json.dumps(verification, ensure_ascii=False),
                },
                trace,
            )
            return ReturnAgentResult(
                answer=self._format_manual_review_answer(
                    item, tracking_number, verification
                ),
                status="manual_review",
                trace=trace,
            )

        if verification.get("status") == "needs_more_information":
            self._invoke_tool(
                "log_return_action",
                {
                    "action": "return_information_needed",
                    "tracking_number": tracking_number,
                    "product_id": item["product_id"],
                    "status": "needs_more_information",
                    "details_json": json.dumps(verification, ensure_ascii=False),
                },
                trace,
            )
            return ReturnAgentResult(
                answer=self._format_missing_info_answer(item, tracking_number, verification),
                status="needs_more_information",
                trace=trace,
            )

        self._invoke_tool(
            "log_return_action",
            {
                "action": "return_denied",
                "tracking_number": tracking_number,
                "product_id": item["product_id"],
                "status": verification.get("status", "not_eligible"),
                "details_json": json.dumps(verification, ensure_ascii=False),
            },
            trace,
        )
        return ReturnAgentResult(
            answer=self._format_denial_answer(item, tracking_number, verification, policy_context),
            status="not_eligible",
            trace=trace,
        )

    @staticmethod
    def _format_success_answer(
        item: dict[str, Any],
        verification: dict[str, Any],
        label: dict[str, Any],
    ) -> str:
        reasons = "\n".join(f"- {reason}" for reason in verification.get("reasons", []))
        warnings = "\n".join(f"- {warning}" for warning in verification.get("warnings", []))
        warning_block = f"\n\n**Important notes:**\n{warnings}" if warnings else ""
        instructions = "\n".join(f"- {line}" for line in label.get("instructions", []))
        label_visual = ""
        if label.get("label_svg"):
            label_visual = (
                "\n\n<!-- RETURN_LABEL_SVG_START -->\n"
                f"{label['label_svg']}\n"
                "<!-- RETURN_LABEL_SVG_END -->"
            )

        return (
            "Your return request was approved, and I generated a return label.\n\n"
            f"**Item:** {item.get('product_name')} ({item.get('product_id')})\n"
            f"**Return authorization:** `{label.get('return_authorization_id')}`\n"
            f"**Label ID:** `{label.get('label_id')}`\n"
            f"**Return tracking:** `{label.get('tracking_number')}`\n"
            f"**Carrier:** {label.get('carrier')}\n"
            f"**Drop-off deadline:** {label.get('dropoff_deadline')}\n"
            f"**Return shipping cost:** {label.get('shipping_cost_responsibility')}\n\n"
            f"**Eligibility basis:**\n{reasons}\n\n"
            f"**Next steps:**\n{instructions}"
            f"{warning_block}"
            f"{label_visual}"
        )

    @staticmethod
    def _format_missing_info_answer(
        item: dict[str, Any],
        tracking_number: str,
        verification: dict[str, Any],
    ) -> str:
        missing = "\n".join(
            f"- {value}" for value in verification.get("missing_information", [])
        )
        warnings = "\n".join(f"- {warning}" for warning in verification.get("warnings", []))
        warning_block = f"\n\n**Important notes:**\n{warnings}" if warnings else ""
        return (
            "I can continue the return request, but I need a little more information first.\n\n"
            f"**Order:** {tracking_number}\n"
            f"**Item:** {item.get('product_name')} ({item.get('product_id')})\n\n"
            f"Please confirm:\n{missing}"
            f"{warning_block}"
        )

    @staticmethod
    def _format_manual_review_answer(
        item: dict[str, Any],
        tracking_number: str,
        verification: dict[str, Any],
    ) -> str:
        reasons = "\n".join(f"- {reason}" for reason in verification.get("reasons", []))
        missing = "\n".join(
            f"- {value}" for value in verification.get("missing_information", [])
        )
        missing_block = f"\n\n**A human specialist will need:**\n{missing}" if missing else ""
        policy_basis = "\n".join(
            f"- {rule}" for rule in verification.get("policy_basis", [])[:3]
        )
        warnings = "\n".join(f"- {warning}" for warning in verification.get("warnings", []))
        warning_block = f"\n\n**Important notes:**\n{warnings}" if warnings else ""

        return (
            "Thanks for letting me know. Since this return depends on photo evidence, "
            "I will route this case to a human support specialist for review before a "
            "return label is generated.\n\n"
            f"**Order:** {tracking_number}\n"
            f"**Item:** {item.get('product_name')} ({item.get('product_id')})\n\n"
            f"**Why a specialist needs to review it:**\n{reasons}"
            f"{missing_block}\n\n"
            f"**Policy basis:**\n{policy_basis}\n\n"
            "The next step is a human handoff: a support specialist can continue from "
            "this chat, collect the photo evidence, review the claim, and then decide "
            "whether the return is eligible for a label."
            f"{warning_block}"
        )

    @staticmethod
    def _format_denial_answer(
        item: dict[str, Any],
        tracking_number: str,
        verification: dict[str, Any],
        policy_context: str,
    ) -> str:
        reasons = "\n".join(f"- {reason}" for reason in verification.get("reasons", []))
        policy_basis = "\n".join(f"- {rule}" for rule in verification.get("policy_basis", [])[:3])
        warnings = "\n".join(f"- {warning}" for warning in verification.get("warnings", []))
        warning_block = f"\n\n**Important notes:**\n{warnings}" if warnings else ""
        context_note = (
            "\n\nThis decision was checked against the return policy context retrieved from the knowledge base."
            if policy_context
            else ""
        )
        return (
            "I cannot generate a return label for this request.\n\n"
            f"**Order:** {tracking_number}\n"
            f"**Item:** {item.get('product_name')} ({item.get('product_id')})\n\n"
            f"**Reason:**\n{reasons}\n\n"
            f"**Policy basis:**\n{policy_basis}"
            f"{warning_block}"
            f"{context_note}"
        )


def run_return_agent(user_input: str, policy_context: str = "") -> ReturnAgentResult:
    """Run the EcoMarket return automation agent for one user request."""
    return ReturnAutomationAgent().run(user_input, policy_context=policy_context)
