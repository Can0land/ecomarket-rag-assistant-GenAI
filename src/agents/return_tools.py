"""LangChain tools used by the EcoMarket return automation agent."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool

from src.services.order_service import get_order

LOG_PATH = Path("logs/return_agent_actions.jsonl")

ECO_MARKET_ERROR_REASONS = {
    "damaged",
    "defective",
    "incorrect_item",
    "wrong_item",
    "spoiled",
    "expired_on_arrival",
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _current_date(value: str | None = None) -> date:
    parsed = _parse_date(value or os.getenv("ECOMARKET_AGENT_TODAY"))
    return parsed or date.today()


def _normalize_reason(value: str | None) -> str:
    lowered = (value or "").strip().lower()
    if any(word in lowered for word in ("wrong", "incorrect")):
        return "incorrect_item"
    if any(word in lowered for word in ("damage", "damaged", "broken")):
        return "damaged"
    if "defect" in lowered:
        return "defective"
    if any(word in lowered for word in ("spoiled", "spoilt")):
        return "spoiled"
    if "expired" in lowered or "expiration" in lowered:
        return "expired_on_arrival"
    if any(word in lowered for word in ("changed mind", "no longer", "do not want", "don't want")):
        return "change_of_mind"
    return lowered or "unspecified"


def _find_item(order: dict[str, Any], product_id: str) -> dict[str, Any] | None:
    normalized = product_id.strip().upper()
    for item in order.get("items", []):
        if item.get("product_id", "").strip().upper() == normalized:
            return item
    return None


def _ellipsize(value: str, max_chars: int) -> str:
    """Keep SVG text inside compact label cells."""
    return value if len(value) <= max_chars else value[: max_chars - 3] + "..."


def _barcode_lines(value: str, x: int, y: int, height: int, max_width: int) -> str:
    """Build deterministic SVG barcode bars from a label value."""
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest() * 2
    lines: list[str] = []
    cursor = x
    end = x + max_width

    for char in digest:
        width = 1 + (int(char, 16) % 3)
        if cursor + width > end:
            break
        lines.append(
            f'<rect x="{cursor}" y="{y}" width="{width}" height="{height}" fill="#111827" />'
        )
        cursor += width + 2

    return "\n".join(lines)


def _build_return_label_svg(
    *,
    label_id: str,
    return_authorization_id: str,
    return_tracking_number: str,
    carrier: str,
    dropoff_deadline: str,
    shipping_cost_responsibility: str,
    tracking_number: str,
    product_id: str,
    product_name: str,
    region: str,
) -> str:
    """Create a printable SVG return label for the chat UI."""
    safe = {
        "label_id": escape(label_id),
        "return_authorization_id": escape(return_authorization_id),
        "return_tracking_number": escape(return_tracking_number),
        "carrier": escape(carrier),
        "dropoff_deadline": escape(dropoff_deadline),
        "shipping_cost_responsibility": escape(shipping_cost_responsibility),
        "tracking_number": escape(tracking_number.upper()),
        "product_id": escape(product_id.upper()),
        "product_name": escape(_ellipsize(product_name, 31)),
        "region": escape(region),
    }
    barcode = _barcode_lines(return_tracking_number, x=330, y=220, height=78, max_width=158)
    small_barcode = _barcode_lines(label_id, x=14, y=301, height=35, max_width=160)

    return f"""
<div style="max-width:540px;margin:14px 0 4px 0;">
  <svg viewBox="0 0 514 370" role="img" aria-label="EcoMarket return label" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#ffffff;">
    <defs>
      <clipPath id="largeBarcodeClip">
        <rect x="258" y="218" width="242" height="82" />
      </clipPath>
      <clipPath id="smallBarcodeClip">
        <rect x="13" y="300" width="244" height="56" />
      </clipPath>
    </defs>

    <rect x="13" y="14" width="488" height="342" fill="#ffffff" stroke="#111827" stroke-width="2"/>

    <rect x="13" y="14" width="104" height="64" fill="#f8fafc" stroke="#111827" stroke-width="2"/>
    <text x="65" y="61" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="54" font-weight="900" fill="#111827">R</text>
    <rect x="117" y="14" width="384" height="64" fill="#f8fafc" stroke="#111827" stroke-width="2"/>
    <text x="135" y="35" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#111827">TO:</text>
    <text x="135" y="56" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="900" fill="#111827">EcoMarket Returns Center</text>
    <text x="135" y="73" font-family="Arial, Helvetica, sans-serif" font-size="13" fill="#111827">125 Green Loop Ave, Portland, OR 97209</text>

    <rect x="13" y="78" width="488" height="40" fill="#111827"/>
    <text x="257" y="104" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="900" fill="#ffffff" letter-spacing="5">RETURN LABEL</text>

    <rect x="13" y="118" width="488" height="42" fill="#f8fafc" stroke="#111827" stroke-width="2"/>
    <text x="27" y="136" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="900" fill="#111827">FROM:</text>
    <text x="84" y="136" font-family="Arial, Helvetica, sans-serif" font-size="14" font-weight="900" fill="#111827">EcoMarket Customer - Order {safe["tracking_number"]}</text>
    <text x="84" y="153" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#111827">Return region: {safe["region"]}</text>

    <rect x="13" y="160" width="244" height="58" fill="#ffffff" stroke="#111827" stroke-width="2"/>
    <text x="27" y="179" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="900" fill="#111827">RMA:</text>
    <text x="27" y="203" font-family="Arial, Helvetica, sans-serif" font-size="16" font-weight="900" fill="#111827">{safe["return_authorization_id"]}</text>
    <rect x="257" y="160" width="244" height="58" fill="#ffffff" stroke="#111827" stroke-width="2"/>
    <text x="271" y="179" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="900" fill="#111827">LABEL ID:</text>
    <text x="271" y="203" font-family="Arial, Helvetica, sans-serif" font-size="16" font-weight="900" fill="#111827">{safe["label_id"]}</text>

    <rect x="13" y="218" width="244" height="82" fill="#ffffff" stroke="#111827" stroke-width="2"/>
    <text x="27" y="241" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="900" fill="#111827">PRODUCT:</text>
    <text x="27" y="263" font-family="Arial, Helvetica, sans-serif" font-size="16" font-weight="900" fill="#111827">{safe["product_id"]}</text>
    <text x="27" y="283" font-family="Arial, Helvetica, sans-serif" font-size="13" fill="#111827">{safe["product_name"]}</text>
    <rect x="257" y="218" width="244" height="82" fill="#ffffff" stroke="#111827" stroke-width="2"/>
    <g clip-path="url(#largeBarcodeClip)">
      {barcode}
    </g>

    <rect x="13" y="300" width="244" height="56" fill="#ffffff" stroke="#111827" stroke-width="2"/>
    <g clip-path="url(#smallBarcodeClip)">
      {small_barcode}
    </g>
    <text x="135" y="350" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#111827">{safe["label_id"]}</text>

    <rect x="257" y="300" width="244" height="56" fill="#f8fafc" stroke="#111827" stroke-width="2"/>
    <text x="271" y="320" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="900" fill="#111827">CARRIER:</text>
    <text x="341" y="320" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#111827">{safe["carrier"]}</text>
    <text x="271" y="340" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="900" fill="#111827">DROP BY:</text>
    <text x="341" y="340" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#111827">{safe["dropoff_deadline"]}</text>
  </svg>
</div>
""".strip()


def _base_result(
    *,
    status: str,
    tracking_number: str,
    product_id: str,
    eligible: bool = False,
    reasons: list[str] | None = None,
    missing_information: list[str] | None = None,
    policy_basis: list[str] | None = None,
    warnings: list[str] | None = None,
    shipping_cost_responsibility: str = "undetermined",
    order: dict[str, Any] | None = None,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "eligible": eligible,
        "tracking_number": tracking_number,
        "product_id": product_id,
        "product_name": (item or {}).get("product_name", "unknown"),
        "order_status": (order or {}).get("status", "unknown"),
        "reasons": reasons or [],
        "missing_information": missing_information or [],
        "policy_basis": policy_basis or [],
        "warnings": warnings or [],
        "shipping_cost_responsibility": shipping_cost_responsibility,
    }


def verify_return_eligibility(
    tracking_number: str,
    product_id: str,
    return_reason: str = "",
    unused: bool | None = None,
    packaging_intact: bool | None = None,
    photo_evidence: bool | None = None,
    reported_within_48h: bool | None = None,
    current_date: str | None = None,
) -> dict[str, Any]:
    """Verify whether a product from an EcoMarket order is eligible for return."""
    order = get_order(tracking_number)
    if not order:
        return _base_result(
            status="error",
            tracking_number=tracking_number,
            product_id=product_id,
            reasons=["The order was not found in EcoMarket records."],
        )

    item = _find_item(order, product_id)
    if not item:
        return _base_result(
            status="error",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            reasons=["The requested product is not part of this order."],
        )

    reasons: list[str] = []
    warnings: list[str] = []
    policy_basis = [
        "Returns must be requested within 30 calendar days from delivery.",
        "The item must be unused and in original condition with packaging intact.",
        "Perishable goods are not returnable unless damaged, spoiled, defective, or incorrectly shipped.",
        "Damaged or incorrect item claims require photo evidence and must be reported within 48 hours.",
    ]
    missing: list[str] = []

    if order.get("status") != "Delivered":
        return _base_result(
            status="not_eligible",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=[
                f"The order status is '{order.get('status')}', so a return label cannot be generated before delivery."
            ],
            policy_basis=policy_basis,
        )

    delivery_date = _parse_date(order.get("estimated_delivery"))
    today = _current_date(current_date)
    if delivery_date is None:
        return _base_result(
            status="needs_more_information",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            missing_information=["the actual delivery date"],
            policy_basis=policy_basis,
        )

    days_since_delivery = (today - delivery_date).days
    if days_since_delivery > 30:
        return _base_result(
            status="not_eligible",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=[
                f"The estimated delivery date was {delivery_date.isoformat()}, which is {days_since_delivery} days ago."
            ],
            policy_basis=policy_basis,
        )

    if days_since_delivery < 0:
        return _base_result(
            status="not_eligible",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=["The estimated delivery date is still in the future."],
            policy_basis=policy_basis,
        )

    reason = _normalize_reason(return_reason)
    is_ecomarket_error = reason in ECO_MARKET_ERROR_REASONS
    is_perishable = bool(item.get("perishable"))
    category = str(item.get("category", "")).lower()

    if order.get("shipping_region") not in {"US-East", "US-West"}:
        warnings.append(
            "This order may be subject to international return restrictions, duties, or additional shipping costs."
        )

    if is_perishable and not is_ecomarket_error:
        return _base_result(
            status="not_eligible",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=[
                "The item is perishable, and EcoMarket only accepts perishable returns when the product arrived damaged, spoiled, defective, or incorrect."
            ],
            policy_basis=policy_basis,
            warnings=warnings,
        )

    if is_ecomarket_error:
        if photo_evidence is not True:
            missing.append("photo evidence of the damaged, spoiled, defective, or incorrect item")
        if reported_within_48h is not True:
            missing.append("confirmation that the issue was reported within 48 hours of delivery")

        reasons.append(
            "This claim depends on photo evidence, but the current chat cannot upload or validate images."
        )
        reasons.append(
            "A human support specialist must review the evidence before a return label can be authorized."
        )

        return _base_result(
            status="manual_review",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=reasons,
            missing_information=missing,
            policy_basis=policy_basis,
            warnings=warnings,
            shipping_cost_responsibility="pending manual review",
        )

    if category in {"personal care", "hygiene"} and unused is False:
        return _base_result(
            status="not_eligible",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=["Opened or used hygiene and personal care products are not returnable."],
            policy_basis=policy_basis,
            warnings=warnings,
        )

    if unused is False:
        return _base_result(
            status="not_eligible",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=["The return policy requires the item to be unused and in original condition."],
            policy_basis=policy_basis,
            warnings=warnings,
        )

    if packaging_intact is False:
        return _base_result(
            status="not_eligible",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            reasons=["The return policy requires original packaging, labels, and accessories to be intact."],
            policy_basis=policy_basis,
            warnings=warnings,
        )

    if unused is not True:
        missing.append("confirmation that the item is unused and in original condition")
    if packaging_intact is not True:
        missing.append("confirmation that original packaging, labels, and accessories are intact")

    if missing:
        return _base_result(
            status="needs_more_information",
            tracking_number=tracking_number,
            product_id=product_id,
            order=order,
            item=item,
            missing_information=missing,
            policy_basis=policy_basis,
            warnings=warnings,
        )

    reasons.append(
        f"The request is within the 30-day return window ({days_since_delivery} days since estimated delivery)."
    )
    reasons.append("The item is unused and the original packaging is intact.")

    return _base_result(
        status="eligible",
        eligible=True,
        tracking_number=tracking_number,
        product_id=product_id,
        order=order,
        item=item,
        reasons=reasons,
        policy_basis=policy_basis,
        warnings=warnings,
        shipping_cost_responsibility="customer",
    )


def generate_return_label(
    tracking_number: str,
    product_id: str,
    shipping_cost_responsibility: str = "customer",
    current_date: str | None = None,
) -> dict[str, Any]:
    """Generate a simulated return label for an eligible EcoMarket return."""
    order = get_order(tracking_number)
    today = _current_date(current_date)
    seed = f"{tracking_number.upper()}:{product_id.upper()}:{today.isoformat()}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8].upper()
    region = (order or {}).get("shipping_region", "US-East")
    item = _find_item(order or {}, product_id) or {}
    carrier = "EcoShip Returns"
    if region in {"Europe", "Canada"}:
        carrier = "EcoShip International Returns"
    label_id = f"RTL-{digest}"
    return_authorization_id = f"RMA-{tracking_number.upper()}-{product_id.upper()}"
    return_tracking_number = f"RET{digest}"
    dropoff_deadline = (today + timedelta(days=14)).isoformat()
    label_svg = _build_return_label_svg(
        label_id=label_id,
        return_authorization_id=return_authorization_id,
        return_tracking_number=return_tracking_number,
        carrier=carrier,
        dropoff_deadline=dropoff_deadline,
        shipping_cost_responsibility=shipping_cost_responsibility,
        tracking_number=tracking_number,
        product_id=product_id,
        product_name=item.get("product_name", "EcoMarket item"),
        region=region,
    )

    return {
        "status": "generated",
        "return_authorization_id": return_authorization_id,
        "label_id": label_id,
        "carrier": carrier,
        "tracking_number": return_tracking_number,
        "dropoff_deadline": dropoff_deadline,
        "shipping_cost_responsibility": shipping_cost_responsibility,
        "label_svg": label_svg,
        "instructions": [
            "Pack the item securely with all original packaging, labels, and accessories.",
            "Print the generated label shown below and attach it to the outside of the package.",
            "Use a trackable drop-off point before the deadline shown on the label.",
        ],
    }


def log_return_action(
    action: str,
    tracking_number: str = "",
    product_id: str = "",
    status: str = "",
    details_json: str = "{}",
) -> dict[str, Any]:
    """Append an agent action record to the local return-agent audit log."""
    try:
        details = json.loads(details_json) if details_json else {}
    except json.JSONDecodeError:
        details = {"raw_details": details_json}

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "tracking_number": tracking_number,
        "product_id": product_id,
        "status": status,
        "details": details,
    }

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"status": "logged", "path": str(LOG_PATH)}


def build_return_tools() -> list[StructuredTool]:
    """Create the LangChain tools used by the return automation agent."""
    return [
        StructuredTool.from_function(verify_return_eligibility),
        StructuredTool.from_function(generate_return_label),
        StructuredTool.from_function(log_return_action),
    ]
