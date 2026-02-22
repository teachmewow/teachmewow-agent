import sys
import types

sys.modules.setdefault("helix", types.ModuleType("helix"))

from app.application.agent.tools import get_all_tools
from app.application.agent.tools.build_lookup import build_lookup
from app.application.agent.tools.guide_context_lookup import guide_context_lookup
from app.application.agent.tools.list_builds import list_builds


def test_list_builds_schema_uses_only_canonical_literals() -> None:
    schema = list_builds.args_schema.model_json_schema()
    properties = schema.get("properties", {})

    assert "char_info" not in properties
    assert properties["environment"]["anyOf"][0]["enum"] == [
        "raid",
        "mythic_plus",
        "delves",
    ]
    assert properties["mode"]["anyOf"][0]["enum"] == ["single", "aoe"]
    assert properties["hero_talent"]["anyOf"][0]["enum"] == ["slayer", "colossus"]


def test_legacy_build_reasoning_context_tool_is_not_registered() -> None:
    tool_names = {tool.name for tool in get_all_tools()}
    assert "build_reasoning_context" not in tool_names


def test_guide_context_lookup_model_visible_args_are_minimal() -> None:
    schema = guide_context_lookup.args_schema.model_json_schema()
    properties = schema.get("properties", {})

    assert set(properties.keys()) == {"question", "source_id", "result_limit"}


def test_build_lookup_model_visible_args_are_minimal() -> None:
    schema = build_lookup.args_schema.model_json_schema()
    properties = schema.get("properties", {})
    assert set(properties.keys()) == {"build_id"}
