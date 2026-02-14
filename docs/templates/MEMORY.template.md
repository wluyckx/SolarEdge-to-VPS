# Agent Memory — {{PROJECT_NAME}}

<!-- TEMPLATE: This file is the agent's persistent memory across sessions. -->
<!-- TEMPLATE: It is auto-loaded into the system prompt (first 200 lines only). -->
<!-- TEMPLATE: Keep it concise — move detail into topic files linked at the bottom. -->
<!-- TEMPLATE: Location: {{MEMORY_PATH}}/memory/MEMORY.md -->
<!-- TEMPLATE: Replace all {{PLACEHOLDER}} values and remove TEMPLATE comments. -->

<!-- TEMPLATE: IMPORTANT — 200-line hard limit. Lines beyond 200 are silently truncated. -->
<!-- TEMPLATE: If approaching 200 lines, move detail into topic files and replace with links. -->

## Current State ({{DATE}})

### Active Work
- {{CURRENT_WORK_DESCRIPTION}}
- {{ACTIVE_STORY_OR_TASK}}

### Completed This Session
- {{COMPLETED_ITEM_1}}
- {{COMPLETED_ITEM_2}}

### Project Status
| Artifact | Status |
|----------|--------|
| CLAUDE.md | {{STATUS}} |
| Architecture.md | {{STATUS}} |
| docs/BACKLOG.md | {{STATUS}} |
| MEMORY.md | {{STATUS}} |
| {{PROJECT_ARTIFACT}} | {{STATUS}} |

## Key Decisions
- {{KEY_DECISION_1}}
- {{KEY_DECISION_2}}
- {{KEY_DECISION_3}}

## Architecture Summary
- **Language**: {{LANGUAGE}}
- **Framework**: {{FRAMEWORK}}
- **State**: {{STATE_MANAGEMENT}}
- **HTTP**: {{HTTP_CLIENT}}
- **Storage**: {{DATABASE}}
- **Testing**: {{TEST_FRAMEWORK}}
- **Pattern**: {{ARCHITECTURE_PATTERN}}

## Story Priority (Next Up)
1. STORY-{{XXX}}: {{TITLE}} ({{COMPLEXITY}})
2. STORY-{{XXX}}: {{TITLE}} ({{COMPLEXITY}})
3. STORY-{{XXX}}: {{TITLE}} ({{COMPLEXITY}})

## Companion Projects
<!-- TEMPLATE: Remove this section if not applicable -->
- {{COMPANION_NAME}} at `{{COMPANION_PATH}}`
- Provides: {{WHAT_IT_PROVIDES}}

## Resume Checklist
1. `git log --oneline -20`
2. Read this file
3. Check `docs/BACKLOG.md` for current priorities
4. `{{TEST_COMMAND}}` (once project exists)
5. {{ADDITIONAL_RESUME_STEP}}

## Patterns and Lessons
- [patterns.md](patterns.md) — coding patterns, gotchas, lessons learned
- [design.md](design.md) — design tokens, UI decisions, rejection log
<!-- TEMPLATE: Add topic file links as they are created -->
<!-- TEMPLATE: Topic files are NOT auto-loaded — agent reads on demand -->
