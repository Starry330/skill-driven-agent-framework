# Tasks

- [x] Task 1: Environment Setup & Core Structure
    - [x] 1.1: Initialize Python project with `pyproject.toml` and dependencies (`langgraph`, `langchain`, `pydantic`, `mcp`).
    - [x] 1.2: Create directory structure (`agent_framework/{core, memory, soul, skills, mcp, tools}`).
    - [x] 1.3: Define core `AgentState` using Pydantic/TypedDict for LangGraph.

- [x] Task 2: Soul Engine Implementation
    - [x] 2.1: Implement `Soul` class to represent agent identity.
    - [x] 2.2: Implement `SoulLoader` to parse `soul.md` (YAML frontmatter + Markdown content).
    - [x] 2.3: Implement `Guardrail` parser and runtime interceptor based on `soul.md`.

- [x] Task 3: Skill Engine Implementation
    - [x] 3.1: Define `Skill` data structure (metadata, body, schema).
    - [x] 3.2: Implement `SkillRegistry` to scan and index `SKILL.md` files.
    - [x] 3.3: Implement `SkillSelector` node in LangGraph for progressive disclosure (metadata-first, load body on demand).

- [x] Task 4: Memory System Implementation
    - [x] 4.1: Integrate LangGraph `MemorySaver` (Checkpointer) for short-term thread persistence.
    - [x] 4.2: Implement `LongTermMemory` interface (Store) for semantic storage.
    - [x] 4.3: Implement `AutoCompact` middleware/node to summarize history when token count exceeds threshold.

- [x] Task 5: MCP Integration Gateway
    - [x] 5.1: Implement `MCPClient` wrapper to connect to MCP servers (stdio/http).
    - [x] 5.2: Implement tool adaptation layer to convert MCP tools to LangChain/LangGraph compatible tools.
    - [x] 5.3: Implement `ToolNode` with execution sandbox (mock/interface first) and result handling.

- [x] Task 6: Orchestration & Workflow
    - [x] 6.1: Build the main `StateGraph` connecting: `Input -> Retrieve(Skills/Mem) -> Agent(LLM) -> Tools -> Output`.
    - [x] 6.2: Implement `HumanInTheLoop` (HITL) checkpoint for sensitive tool execution.
    - [x] 6.3: Implement `Supervisor` pattern for multi-agent routing (optional MVP, but structure needed).

- [x] Task 7: Verification & Example
    - [x] 7.1: Create a sample `soul.md` (e.g., "ResearchAssistant") and `SKILL.md` (e.g., "WebSearch").
    - [x] 7.2: Create a runner script `run_agent.py` to instantiate and execute the agent.
    - [x] 7.3: Verify persistence and memory recall across sessions.
