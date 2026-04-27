from __future__ import annotations

from typing import Any, Callable

from temu_y2_women.public_source_adapters.marieclaire_editorial import parse_marieclaire_editorial_html
from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html


Adapter = Callable[[dict[str, Any], str, str], dict[str, Any]]


def resolve_public_source_adapter(adapter_id: str) -> Adapter:
    adapters = {
        "whowhatwear_editorial_v1": parse_whowhatwear_editorial_html,
        "marieclaire_editorial_v1": parse_marieclaire_editorial_html,
    }
    try:
        return adapters[adapter_id]
    except KeyError as error:
        raise ValueError(f"unsupported public source adapter: {adapter_id}") from error
