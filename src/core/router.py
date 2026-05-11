# Keyword sets that trigger each intent.
# More specific checks run first; fallback is 'general'.

ABUSIVE_LANGUAGE_KEYWORDS = {
    "fuck you",
    "go fuck",
    "shut up",
    "asshole",
    "bitch",
    "idiot",
    "stupid bot",
    "mierda",
    "imbecil",
    "idiota",
}

RETURN_REQUEST_KEYWORDS = {
    "return label",
    "generate label",
    "create label",
    "start a return",
    "initiate a return",
    "process a return",
    "return request",
    "return authorization",
    "rma",
    "want to return",
    "need to return",
    "would like to return",
    "send it back",
    "send back",
}

ORDER_KEYWORDS = {
    "order",
    "pedido",
    "tracking",
    "shipment",
    "package",
    "delivery",
    "eco201",
    "where is my",
}

RETURN_KEYWORDS = {
    "return",
    "devol",
    "refund",
    "reembolso",
    "exchange",
    "money back",
    "send back",
}

SHIPPING_KEYWORDS = {
    "shipping",
    "ship",
    "envio",
    "envío",
    "freight",
    "carrier",
    "dispatch",
    "international",
    "express",
    "standard shipping",
    "delivery time",
    "how long",
    "free shipping",
}

PRODUCT_KEYWORDS = {
    "product",
    "item",
    "catalog",
    "ingredient",
    "organic",
    "sustainable",
    "eco-friendly",
    "material",
    "bamboo",
    "milk",
    "beef",
    "soap",
    "bread",
    "protein",
}

INVENTORY_KEYWORDS = {
    "stock",
    "available",
    "availability",
    "inventory",
    "in stock",
    "out of stock",
    "perishable",
    "expire",
    "expiration",
    "shelf life",
    "manufacturing",
    "warehouse",
    "batch",
    "p00",
}

HUMAN_KEYWORDS = {
    "complaint",
    "queja",
    "upset",
    "angry",
    "frustrated",
    "unacceptable",
    "terrible",
    "worst",
    "speak to a human",
    "speak to agent",
    "escalate",
    "supervisor",
    "manager",
}


def detect_intent(text: str) -> str:
    """Classify user input into one of nine intents using keyword matching.

    Precedence: abusive_language > human > return_request > order_status >
    return_policy > shipping > inventory > product > general.

    Args:
        text: Raw user message.

    Returns:
        Intent string.
    """
    lowered = text.lower()

    if _contains_abusive_language(lowered):
        return "abusive_language"

    if any(kw in lowered for kw in HUMAN_KEYWORDS):
        return "human"

    if _is_return_request(lowered):
        return "return_request"

    if any(kw in lowered for kw in ORDER_KEYWORDS):
        return "order_status"

    if any(kw in lowered for kw in RETURN_KEYWORDS):
        return "return_policy"

    if any(kw in lowered for kw in SHIPPING_KEYWORDS):
        return "shipping"

    if any(kw in lowered for kw in INVENTORY_KEYWORDS):
        return "inventory"

    if any(kw in lowered for kw in PRODUCT_KEYWORDS):
        return "product"

    return "general"


def _contains_abusive_language(lowered: str) -> bool:
    """Detect direct abusive language toward the assistant."""
    return any(kw in lowered for kw in ABUSIVE_LANGUAGE_KEYWORDS)


def _is_return_request(lowered: str) -> bool:
    """Return True when a message asks the agent to perform a return action."""
    if any(kw in lowered for kw in RETURN_REQUEST_KEYWORDS):
        return True

    has_return_language = any(kw in lowered for kw in RETURN_KEYWORDS)
    has_order_or_product = any(token in lowered for token in ("eco201", "p00", "order", "product", "item"))
    has_action = any(
        token in lowered
        for token in ("start", "initiate", "create", "generate", "process", "request", "label")
    )

    return has_return_language and has_order_or_product and has_action
