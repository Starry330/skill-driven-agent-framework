# Checklist

- [x] Environment is set up with necessary dependencies.
- [x] `AgentState` is defined and supports required context.
- [x] `SoulLoader` correctly parses `soul.md` attributes (Role, Goal, Guardrails).
- [x] `SkillRegistry` correctly indexes `SKILL.md` files.
- [x] Progressive disclosure mechanism works: only skill metadata is initially visible, body is loaded on demand.
- [ ] LangGraph runtime executes the basic loop (Think -> Act -> Observe).
- [x] Short-term memory persists across steps within a thread.
- [x] Long-term memory stores and retrieves semantic information.
- [x] Auto-compact logic triggers when context is full.
- [x] MCP tools are discoverable and executable by the agent.
- [x] HITL mechanism pauses execution for sensitive actions.
- [x] Sample agent runs successfully end-to-end.
