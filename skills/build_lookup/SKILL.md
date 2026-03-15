---
name: build-lookup
description: Find, list, and show WoW builds for the user's class and spec.
---

# Build Lookup

## Default flow
Call `list_builds` **once with no filters** — it returns every build for the character's class/spec.
Present results grouped by environment (Raid / Mythic+ / Delves).

## Only add filters when the user is specific
If the user says "slayer M+" or "raid ST", add those filters. Otherwise, no filters. You need to pay attention to the equivalences between the user's language and the filters Literals types in tool description.

## NEVER call list_builds more than once per turn unless the user asks for a different filter.

## After listing
Ask which build the user wants to open. When they pick one, call `build_lookup(build_id)` for the full talent tree and import code.

# Next steps:

After picking up a build, probably user will ask coaching for it, and you need to call the `build-coaching` skill to provide the coaching.