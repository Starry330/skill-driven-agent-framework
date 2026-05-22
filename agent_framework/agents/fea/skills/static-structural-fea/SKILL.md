---
name: static-structural-fea
description: Build a static structural FEA preprocessing plan from an STP/STEP model.
triggers:
  - fea
  - static
  - structural
  - 静力学
  - 有限元
  - STP
  - STEP
slash_command: fea
required_tools:
  - analyze_stp_file
  - get_multiview
permissions:
  - local_files
input_schema:
  type: object
  properties:
    file_path:
      type: string
output_schema:
  type: string
subagent_allowed: false
dependencies: []
availability_checks: []
enabled: true
metadata:
  category: engineering
---
Use this skill for static structural analysis planning around CAD geometry.

Execution notes:
1. Read or confirm the STP/STEP file path.
2. Run `analyze_stp_file` to inspect topology and geometry complexity.
3. Run `get_multiview` when visual evidence helps identify likely load paths or danger zones.
4. Output a structured plan with assumptions, constraint/load candidates, meshing strategy, validation notes, and missing inputs.
