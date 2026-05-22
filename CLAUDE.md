# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Skill-driven AI agent framework built with LangGraph + LangChain. Defines agents via specifications, workspace documents, skills, and governed tools with SQLite-backed memory. Includes a Builder Agent that generates new agents from natural language.

## Common Commands

```bash
# Install in editable mode
pip install -e .

# Run all tests
python -m unittest discover -s tests -v

# Run a single test file
python -m unittest tests.unit.test_skill_router

# Run a single test method
python -m unittest tests.unit.test_skill_router.SkillRouterTest.test_web_search_skill_routes_for_search_query

# Linting (Ruff) - configured in pyproject.toml
ruff check agent_framework/

# Auto-fix linting issues
ruff check agent_framework/ --fix

# Type checking (mypy) - configured in pyproject.toml
mypy agent_framework/
```

## Architecture

**Layered design with Gateway as single entry point:**
- Gateway (`agent_framework/core/gateway.py`) orchestrates: bootstrap → skill routing → tool governance → workflow execution → memory persistence
- Workflow layer (`agent_framework/workflows/`) is LangGraph-based, pure execution engine with no persistence responsibility

**Agent Specification Pattern:**
- Each agent defined by `AgentSpec` dataclass (agent_id, workspace_dir, skills_dirs, llm, tool_policy, memory_namespaces)
- Factory functions `create_<name>_agent()` in `agent_framework/agents/<name>/` return `(AgentSpec, List[ToolSpec])`
- Example: `agent_framework/agents/research/spec.py` defines `create_research_agent()`

**Workspace Documents:**
- Each agent has `workspace/` dir with markdown docs: `AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `memory/MEMORY.md`
- Loaded by `BootstrapLoader` and injected into prompts
- `AGENTS.md`: agent persona and behavior guidelines
- `SOUL.md`: core values and decision-making principles
- `USER.md`: user context and interaction preferences
- `TOOLS.md`: available tools and usage patterns
- `memory/MEMORY.md`: persistent memory index

**Skill Runtime:**
- Skills defined via `SKILL.md` files with YAML frontmatter (name, description, triggers, required_tools, availability_checks)
- Pipeline: `SkillRegistry` loads → `SkillRouter` ranks by trigger match → `SkillRuntime` filters by tool availability
- Skills can define `input_schema` and `output_schema` for structured I/O
- Example: `agent_framework/agents/research/skills/web-search/SKILL.md`

**Tool Governance:**
- `ToolPolicy`: allowlist, denylist, `skill_tool_overrides` (per-skill scoping)
- `side_effect_level` on tools determines approval requirements (`high`/`critical` require approval)
- `AuditLogger` records all tool executions to SQLite
- Tools built via `build_local_tool_spec()` which wraps LangChain tools with metadata

**Memory System:**
- SQLite-backed in `storage/runtime.db`
- Short-term: session transcript + summary + working state (auto-summarized when exceeding limits)
- Long-term: semantic, episodic, user_memory, task_memory, tool_notes namespaces
- `MemoryManager` coordinates between short-term and long-term stores

**Builder Agent:**
- Generates complete agent scaffolds from natural language requirements
- Uses `AgentBlueprint` model to structure output (skills, tools, workspace docs)
- Strict confirmation: user must type exact phrase `确认创建` to write files
- Builder skills in `agent_framework/agents/builder/skills/` handle each generation step

## Key Files

- `agent_framework/__init__.py` - Public API exports (AgentSpec, Gateway, FrameworkSettings, BuilderService)
- `agent_framework/core/gateway.py` - Central orchestrator, manages full agent lifecycle
- `agent_framework/core/agent.py` - AgentSpec dataclass definition
- `agent_framework/config/settings.py` - FrameworkSettings Pydantic model, loaded from `.env`
- `agent_framework/bootstrap/loader.py` - Workspace document loading
- `agent_framework/bootstrap/injector.py` - Injects workspace docs into prompts
- `agent_framework/skills/registry.py` - SkillRegistry loads SKILL.md files
- `agent_framework/skills/router.py` - SkillRouter ranks skills by trigger match
- `agent_framework/skills/runtime.py` - SkillRuntime executes matched skills
- `agent_framework/tools/registry.py` - ToolRegistry manages tool registration
- `agent_framework/tools/policy.py` - ToolPolicyEngine enforces allowlist/denylist
- `agent_framework/tools/executor.py` - ToolExecutor runs tools with governance
- `agent_framework/tools/audit.py` - AuditLogger records all tool executions
- `agent_framework/memory/manager.py` - MemoryManager coordinates memory stores
- `agent_framework/memory/stores/sqlite.py` - SQLite storage backend

## Configuration

- `.env` file for secrets and LLM settings (FrameworkSettings Pydantic model)
- Per-agent LLM settings: `builder_llm`, `research_llm`, `fea_llm` (default provider: MiniMax)
- Ruff: line-length=100, target-version=py310
- Mypy: python_version=3.10, check_untyped_defs=true

## Adding New Agents

1. Create directory under `agent_framework/agents/<name>/` with workspace docs
2. Implement `create_<name>_agent()` factory returning `(AgentSpec, List[ToolSpec])`
3. Add skills under `skills/` with `SKILL.md` files (include YAML frontmatter with triggers, required_tools)
4. Optionally add workflow under `agent_framework/workflows/<name>/`
5. Create chat entry script at repo root (e.g., `chat_with_<name>_agent.py`)

## Adding New Skills

1. Create `SKILL.md` with YAML frontmatter:
   - `name`, `description`, `triggers` (list of keywords/phrases)
   - `required_tools` (tools needed for this skill)
   - `availability_checks` (functions to verify tool availability)
   - `input_schema`/`output_schema` for structured I/O
2. Place under `agent_framework/agents/<agent>/skills/<skill-name>/`
3. Register required tools in the agent's ToolPolicy allowlist
4. Optionally add `skill_tool_overrides` to scope tools per-skill

## Testing Conventions

- Unit tests in `tests/unit/` (test individual components in isolation)
- Integration tests in `tests/integration/` (test component interactions)
- Use `unittest.TestCase` with descriptive method names
- Mock external dependencies (LLMs, HTTP calls) in unit tests
- Integration tests may use real SQLite but mock LLM calls
