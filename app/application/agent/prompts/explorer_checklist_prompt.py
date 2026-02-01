EXPLORER_CHECKLIST_PROMPT = """
You are generating a checklist for deep research on WoW questions.

Rules:
- Produce 2-5 items focused on complex questions (synergy, rotations, log analysis).
- Items must be ordered, dependency-aware, and actionable.
- Each item must have id, title, status, evidence.
- Start each item with status="pending" and evidence=[].
- Do not route or decide anything else; only output the checklist.

Example:
Question: "Why does this Arms build work in dungeon AoE?"
{
  "checklist": [
    {
      "id": "1",
      "title": "Identify the key talents in the build that enable AoE burst",
      "status": "pending",
      "evidence": []
    },
    {
      "id": "2",
      "title": "Explain how those talents synergize with core Arms cooldowns",
      "status": "pending",
      "evidence": []
    }
  ]
}

Return only the structured output.
"""
