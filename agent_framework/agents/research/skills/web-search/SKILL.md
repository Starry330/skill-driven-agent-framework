---
name: web-search
description: Retrieve up-to-date external information from the web when the user asks for recent facts, news, public references, official documentation, or information not available in local knowledge/tools.
triggers:
  - 搜索
  - 查询
  - 查一下
  - 帮我查
  - 上网查
  - 检索
  - research
  - search
  - look up
  - find information
  - browse
slash_command: search
required_tools:
  - web_search
permissions:
  - external_http
input_schema:
  type: object
  properties:
    query:
      type: string
      description: The user's search query or the distilled search intent.
    focus:
      type: string
      description: Optional clarification of what aspect to prioritize, such as official docs, news, pricing, papers, or general overview.
    max_results:
      type: integer
      minimum: 1
      maximum: 10
      default: 5
      description: Maximum number of search results to inspect.
  required:
    - query
output_schema:
  type: object
  properties:
    summary:
      type: string
      description: Concise answer to the user's request.
    key_facts:
      type: array
      items:
        type: string
      description: Verifiable facts found from search results.
    inferences:
      type: array
      items:
        type: string
      description: Reasonable conclusions inferred from the facts, clearly separated from direct evidence.
    sources:
      type: array
      items:
        type: string
      description: Source titles or URLs used in the answer.
  required:
    - summary
subagent_allowed: true
dependencies: []
availability_checks:
  - requires_web_search
enabled: true
metadata:
  category: research
  capability: external_information_retrieval
  priority: medium
---
Use this skill when the user explicitly or implicitly asks for information outside the current workspace or model knowledge, especially for:
- recent events, news, announcements, product updates, prices, policies, or official documentation
- factual verification of uncertain or time-sensitive claims
- public information lookup on people, organizations, technologies, papers, or websites

Do not use this skill when:
- the user only wants rewriting, summarization, translation, brainstorming, or reasoning over content already provided
- the answer can be produced fully from local context, memory, or available internal tools without external lookup

Execution guidelines:
1. Distill the user's request into a focused search query. Keep it short but specific.
2. If the request is broad, prioritize the user's likely intent instead of searching every possible angle.
3. Prefer authoritative and primary sources when available, such as official websites, documentation, publishers, or original announcements.
4. Compare multiple sources when facts may conflict or freshness matters.
5. Separate direct facts from interpretation or inference.
6. If search results are weak or ambiguous, say so explicitly instead of overclaiming.
7. Return a concise answer first, then supporting facts and sources if needed.

Failure handling:
- If the tool is unavailable, explain that external web lookup is currently unavailable.
- If results are insufficient, return the best partial answer and identify what remains uncertain.
