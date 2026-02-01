from app.application.agent.nodes.checklist_update_node import ChecklistUpdateNode
from app.application.agent.state_schema import ChecklistItem


def test_select_next_checklist_id_advances_when_complete() -> None:
    items = [
        ChecklistItem(id="build", title="Find build", status="complete"),
        ChecklistItem(id="rotation", title="Find rotation", status="pending"),
    ]
    next_id = ChecklistUpdateNode._select_next_checklist_id(items, "build")
    assert next_id == "rotation"
