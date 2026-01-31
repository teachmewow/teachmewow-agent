import json

from app.application.agent.streaming import build_langchain_stream_event, format_sse_event


def test_custom_event_is_formatted() -> None:
    event = {"event": "custom", "data": {"kind": "checklist_update", "data": {"id": "a"}}}
    stream_event = build_langchain_stream_event(event)
    sse = format_sse_event(stream_event)
    assert sse.startswith("event: custom")
    payload = json.loads(sse.split("data: ", 1)[1])
    assert payload["event"] == "custom"
    assert payload["data"]["kind"] == "checklist_update"
