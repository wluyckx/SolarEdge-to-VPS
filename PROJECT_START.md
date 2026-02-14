/**
 * Project start guide for new repositories.
 *
 * CHANGELOG:
 * - 2026-02-05: Added Step 4 (Agent Memory) and session continuity protocol
 * - 2026-01-27: Initial creation
 *
 * TODO:
 * - [ ] Confirm exact naming for backlog file if needed
 */

# Project Start Guide

Use this file at the start of a new project to bootstrap the four core docs: templates in docs/templates

1) `CLAUDE.md` — agent rules and workflow gates
2) `Architecture.md` — system design and technical reference
3) `docs/BACKLOG.md` — requirements, stories, and acceptance criteria
4) `.claude/projects/{project}/memory/MEMORY.md` — agent memory for session continuity

---

## Step 1: Create `CLAUDE.md`

**Purpose**
- Defines how work starts, what context is required, and how changes are documented.

**Required sections**
- Clear ownership boundary between the agents. Governance agent handles Claude.md, Architecture.md and docs/backlog.md. Coding agent only works within a clearly scoped task.
- Task Intake Checklist (story ID, requirements, AC, affected areas, DoD)
- Code file documentation standards (CHANGELOG and TODO headers)
- Workflow Summary (consult Architecture + Backlog before coding)
- Documentation update rules
- Session Continuity Protocol (see Step 4 below)

---

## Step 2: Create `Architecture.md`

**Purpose**
- Single source of truth for system structure, tech stack, and decisions.

**Required sections**
- Overview
- Tech Stack
- Directory Structure
- Key Components
- Data Flow
- Design Decisions
- security directives = follow instructions on https://github.com/BehiSecc/VibeSec-Skill
- Integration Points
- Development Patterns
- Development Workflow (commands/tests)
- Testing Strategy = Test-Driven-design
- Environment & Secrets
- Operational Assumptions
- Last updated date

---

## Step 3: Create `docs/BACKLOG.md`

**Purpose**
- Defines the work to do, why, and how to validate it.
***Form***
Use xml strcuture for increased agent readability

**Required sections**
- Definition of Ready <DOR>
- Definition of Done <DOD>
- Story template (Status + Test Plan)
- Sprint or phase breakdown with stories, AC, dependencies
- Progress tracking
- Labels reference (optional)

---

## Step 4: Set Up Agent Memory

**Purpose**
- Provides session continuity across conversation windows.
- The Governance Agent updates memory at end of session; it's auto-loaded at start of next.

**Directory structure**
```
.claude/projects/{project-path}/memory/
├── MEMORY.md          # Always loaded into system prompt (max 200 lines)
├── patterns.md        # Coding patterns, gotchas, lessons learned
└── debugging.md       # (optional) Known issues, workarounds
```

**MEMORY.md required sections**
```markdown
# Agent Memory — {Project Name}

## Current Sprint ({date})

### Active Work
- STORY-XXX: Title — status (agent dispatched / blocked / etc.)

### Awaiting Review
- STORY-YYY: Title — agent completed, needs review

### Key Decisions This Session
- Decision 1
- Decision 2

### Resume Checklist
When starting a new session as Governance Agent:
1. Run `git log --oneline -20` to see what was committed
2. Run `pytest tests/ -q` to see test state
3. Check story status in docs/stories/
4. Check docs/BACKLOG.md for current priorities
5. Read this file for context
```

**Rules**
- Keep `MEMORY.md` under 200 lines (truncated beyond that)
- Use topic files for detailed notes, link from MEMORY.md
- Record insights about what worked, what failed, and why
- Update or remove memories that turn out to be wrong
- Organize by topic, not chronologically

**Add to `CLAUDE.md`**
Include a "Session Continuity Protocol" section that mandates:
- Governance Agent updates `MEMORY.md` before ending any session
- Governance Agent runs Resume Checklist at start of any session
- Coding Agents are warned about concurrent shared-file edits
- State is reconstructed from git + tests, not from memory alone

---

## How the four files interact

- `docs/BACKLOG.md` defines the **what**: docs/stories/, requirements, acceptance criteria, and test plans.
- `Architecture.md` defines the **how**: system constraints, patterns, and architectural decisions (ADR)
- `CLAUDE.md` defines the **rules**: when work can start, how to document changes, and when work is complete.
- `MEMORY.md` provides the **continuity**: what happened last session, what's in progress, how to resume.

**Start of any task**
1) `MEMORY.md` is auto-loaded — check for active work and context from previous sessions.
2) Read `docs/BACKLOG.md` to identify the story and acceptance criteria.
3) Read `Architecture.md` to align with existing patterns and constraints.
4) Follow `CLAUDE.md` to confirm the Task Intake Checklist before coding.

**After any significant change**
- Update `Architecture.md` when structure or decisions change.
- Update `docs/BACKLOG.md` when scope/status changes.
- Update CHANGELOG/TODO headers in touched code files per `CLAUDE.md`.

**End of session**
- Update `MEMORY.md` with active work, decisions, and resume checklist.
- Ensure story statuses in `docs/BACKLOG.md` reflect ground truth.
