CHECKLIST_UPDATE_SYSTEM_PROMPT = """
You are updating a checklist based on messages from the current knowledge explorer run.

Rules:
- Only mark an item complete if the evidence supports it.
- If tool calls returned no results, mark the relevant item complete with an observation stating that no data was found.
- If no new evidence is present for an item, keep its status unchanged.
- evidence must contain short bullet-like strings with key facts.
"""
