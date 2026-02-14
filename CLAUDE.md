# CLAUDE.md — Agent Operating Manual

This file defines **how work is allowed to happen** in the Sungrow-to-VPS pipeline repository.
It has higher authority than all other repository documents except system/user instructions.

**Companion project**: [P1-Edge-VPS](../P1-Edge-VPS/) — a fully separate pipeline for HomeWizard P1 grid data. This repo follows the same architecture patterns but is fully standalone.

---

## 1. Authority & Precedence (Hard Rules)

Instruction precedence, highest to lowest:

1. System + explicit user instructions
2. This file (`CLAUDE.md`) — **cannot be overridden**
3. `Architecture.md`
4. `docs/BACKLOG.md` and story files (`docs/stories/*.md`)
5. Source code and tests

If a request conflicts with a higher-priority source, the agent must refuse.

---

## 2. Agent Responsibility Model (Hard Boundary)

Two logical roles exist. **Both roles are played by the same Claude Code agent.**
The user's request determines which role is active — there is no separate process or
formal handoff. When the user asks to restructure the backlog, research a topic, or
define stories, the agent operates as Governance. When the user asks to implement a
story, the agent operates as Coding Agent. The distinction exists to enforce **what
changes are allowed**, not to model separate systems.

### 2.1 Governance Agent

Activated by: strategic questions, research requests, backlog/architecture/story work,
session management, or any task that shapes *what* gets built rather than *building* it.

Responsible for:

**Research & Strategy**
- Investigating Modbus protocols, Sungrow register maps, WiNet-S behavior
- Evaluating technical approaches before committing to stories

**Documents & Decisions**
- Creating and editing: `CLAUDE.md`, `Architecture.md`, `docs/BACKLOG.md`,
  `docs/stories/*.md`
- Defining scope, acceptance criteria, and test plans for stories
- Proposing and approving Architecture Decision Records (ADRs)

**Backlog & Progress**
- Changing story status (pending / in_progress / done)
- Maintaining the dependency graph and priority order
- Restructuring the backlog when new information invalidates assumptions

**Session Continuity**
- Maintaining agent memory (`MEMORY.md` and topic files)
- Updating MEMORY.md at end of session, running resume checklist at start

**Coordination**
- Dispatching Coding Agent work on specific stories
- Resolving conflicts when parallel agents touch shared files

### 2.2 Coding Agent

Activated by: explicit request to implement a specific story.

Responsible for:
- Implementing code changes within a story's Allowed Scope
- Modifying only files explicitly permitted by that story
- Documenting code changes in a changelog header, including story ID and context
- Following TDD workflow when the story mandates it
- Reporting results back (what was done, what tests pass, what's unresolved)

### 2.3 Hard Restrictions

The Coding Agent must NOT:
- Edit governance or backlog documents
- Change scope, AC, or story status
- Introduce new architecture, dependencies, or patterns not in `Architecture.md`
- Modify files outside a story's Allowed Scope
- Add dependencies not listed in `Architecture.md` Tech Stack

If such changes are required, the Coding Agent must stop and request a
Backlog Update or Architecture Proposal.

---

## 2.4 Session Continuity Protocol

Context windows close. Agent memory bridges the gap.

### How Memory Works

Claude Code **automatically injects** `MEMORY.md` into the system prompt at the start of
every conversation. This is a platform feature — the agent does not need to read or load it
manually. It is always present in context from the first message.

**Key constraints**:
- Only the **first 200 lines** of `MEMORY.md` are loaded. Lines beyond 200 are silently
  truncated. This is a hard platform limit — keep the file concise.
- Memory is **local to this machine**. It lives in `.claude/` outside the git repo and is
  not committed, shared, or synced. If you work from a different machine, memory is empty.
- Memory is a **guide, not gospel**. Git log + test results are the ground truth. Memory
  helps the agent know where to look, not what to believe.

### Memory Directory

```
.claude/projects/-Users-Wim-SolarEdge-to-VPS/memory/
├── MEMORY.md          # Auto-loaded into system prompt (max 200 lines)
├── patterns.md        # Coding patterns, gotchas, lessons learned
└── {topic}.md         # Additional topic files as needed
```

### MEMORY.md — What Goes In (max 200 lines)

Keep this file a concise index of current state. It must contain:

1. **Current State**: What phase the project is in, what's actively being worked on
2. **Key Facts**: Important discoveries, Modbus quirks, architecture decisions
3. **Backlog Status**: Which stories are done/in-progress/blocked
4. **Resume Checklist**: Exact commands to reconstruct state in next session
5. **Links to Topic Files**: Pointers to `patterns.md`, etc. for details

**Do NOT put in MEMORY.md**: session-by-session logs, full research transcripts,
verbose explanations, or anything that belongs in a topic file.

### Governance Agent: End-of-Session Duties

Before ending a session, the Governance Agent **must** update `MEMORY.md` with:
1. **Active Work**: Stories in_progress, which agents were dispatched, expected outcomes
2. **Completed Work**: Stories done this session, test results, commits made
3. **Key Decisions**: Scope changes, cancellations, priority shifts, blockers discovered
4. **Resume Checklist**: Exact commands to reconstruct state in next session

If MEMORY.md approaches 200 lines, move detail into topic files and replace with links.

### Context Window Pressure — Mandatory Memory Write

When the context window exceeds **90% capacity** (indicated by automatic message
compression or a system warning), the agent **must immediately** write current state
to `MEMORY.md` before continuing work. This is a hard rule — do not wait for session end.

### Governance Agent: Start-of-Session Protocol

When starting a new session:
1. `MEMORY.md` is already in context — read it for orientation
2. Run the Resume Checklist commands (typically: `git log`, test suite, check story status)
3. Reconcile: if Coding Agents completed after last session closed, their work shows in
   git log and test results but not in MEMORY.md — update accordingly
4. Update story statuses based on ground truth (code + tests), not memory alone

### Agent Coordination Rules

When dispatching multiple Coding Agents in parallel on related stories:
- Warn each agent about shared files that may be created/modified concurrently
- Agents must **check before creating** shared files
- Agents must **read before editing** shared files
- Expect minor merge conflicts in shared files — Governance resolves after completion

---

## 3. Required Response Modes

Every response must declare **exactly one** mode:

- Analysis — reasoning only
- Task Contract — intake confirmation before coding
- Code Change — implementation only
- Architecture Proposal — ADR, no code
- Backlog Update — story or backlog edits
- Blocked — refusal (mandatory grammar)

---

## 4. Context Loading Rules (Strict)

Before coding, the Coding Agent **must** load (in this order):

### Mandatory (Load First)
1. `CLAUDE.md` — This file (operating manual)
2. `SKILL.md` — Security skill (always apply)
3. `Architecture.md` — Full document, especially:
   - Tech Stack
   - Directory Structure
   - Key Components
   - Development Patterns
   - Testing Strategy
4. Exactly one story file from `docs/stories/`

### Forbidden
- Loading multiple stories simultaneously (load only the one being implemented)
- Unrelated modules not in story's Allowed Scope
- Guessing file structures or API contracts
- Making assumptions about undocumented Modbus register behavior

If required context is missing or ambiguous, the agent is Blocked.

---

## 5. Definition of Ready (Pre-Flight Check)

Before the Coding Agent may begin ANY story, ALL conditions must be true:

### Story Requirements
- [ ] Story status is **pending** or explicitly assigned
- [ ] Story has explicit Acceptance Criteria
- [ ] Story has a Test Plan
- [ ] Story has Dependencies listed (or "None")

### TDD Requirements (for TDD-mandated stories)
- [ ] Story has "Test-First Requirements" section
- [ ] Test fixtures or mocks identified
- [ ] Expected behavior documented (where applicable)
- [ ] Mock strategy defined (for external dependencies)

### Agent Requirements
- [ ] Agent has loaded `CLAUDE.md` (this file)
- [ ] Agent has loaded `SKILL.md` (security skill)
- [ ] Agent has loaded **full** `Architecture.md`
- [ ] Agent has loaded the **single** story file being implemented
- [ ] Agent has NOT loaded other stories

### Architecture Verification
- [ ] Tech stack matches Architecture.md Tech Stack section
- [ ] Directory structure matches Architecture.md Directory Structure section
- [ ] Patterns match Architecture.md Development Patterns section

If ANY condition is false, the agent is Blocked. Do not proceed.

---

## 6. Task Intake Gate (No Exceptions)

No code may be written until a **Task Contract** has been produced and validated.

### Minimum Required Intake
- Story ID (e.g., STORY-001)
- Story file path (e.g., `docs/stories/phase-1-edge-foundation.md`)
- Acceptance Criteria (explicit checklist from story)
- Test Plan (from story)
- Allowed Scope (files/modules to be created or modified)
- Architecture sections consulted (list specific sections)

Missing information means the agent is Blocked.

---

## 7. Task Contract (Required Format)

### Task Contract Template
```
Task Contract

- Story ID: [e.g., STORY-001]
- Story file: [e.g., docs/stories/phase-1-edge-foundation.md]
- Goal (1 sentence): [What this story accomplishes]
- Acceptance Criteria:
  - [ ] AC1: ...
  - [ ] AC2: ...
- Test Plan: [How to verify]
- Intended changes (files/modules):
  - [file1]
  - [file2]
- Out of scope: [What will NOT be changed]
- Architecture consulted:
  - Tech Stack
  - Directory Structure
  - [other relevant sections]
- Stop conditions (what forces escalation):
  - [e.g., "If new dependency needed"]
  - [e.g., "If register map needs updating"]
```

---

## 8. Architecture Change Gate

Any change affecting:
- System structure or layer boundaries
- Data flow between layers
- Dependencies (adding new packages)
- Directory conventions
- Database schema
- API contracts
- Modbus register map

requires:
1. Architecture Proposal
2. Update to `Architecture.md`
3. Explicit approval from Governance Agent before implementation

The Coding Agent must STOP and escalate. Do not proceed with unapproved changes.

---

## 9. Refusal Requirement & Grammar

When blocking, the agent **must** use this exact format:

### Refusal Grammar
```
Blocked

Reason: [One of the defined reasons below]
Missing: [What is needed to proceed]
Action: [What must happen to unblock]
```

### Valid Block Reasons
- `story_not_ready` — Story missing AC, Test Plan, or Dependencies
- `context_not_loaded` — Required documents not loaded
- `scope_violation` — Request exceeds story's Allowed Scope
- `architecture_change` — Change requires ADR approval
- `ambiguous_requirement` — Story or Architecture unclear
- `dependency_not_approved` — New package not in Architecture.md Tech Stack
- `security_vulnerability` — Code introduces a security flaw
- `unvalidated_input` — External input not properly validated
- `secrets_exposed` — Credentials, API keys, or tokens in code
- `hardware_assumption` — Assumption about WiNet-S/inverter behavior not verified

Free-form refusals are NOT allowed. Use the grammar above.

---

## 10. Definition of Done (Enforced)

Work is Done only when:
- [ ] All Acceptance Criteria are satisfied
- [ ] Tests executed per Test Plan
- [ ] No undocumented TODOs introduced
- [ ] Changelog header added to all modified source files
- [ ] Code passes linting (`ruff check edge/src/ vps/src/`)
- [ ] Code passes formatting (`ruff format --check edge/src/ vps/src/`)
- [ ] All tests pass with no failures (`pytest edge/tests/ vps/tests/`)
- [ ] Documentation on all public APIs
- [ ] Security checklist passed (per Section 13)
- [ ] Story status updated by Governance Agent

---

## 11. Code File Documentation Standard

All Python files must include a header:

```python
"""
Module description.

CHANGELOG:
- YYYY-MM-DD: Description (STORY-XXX)

TODO:
- Outstanding items
"""
```

### Rules
- CHANGELOG entry required for every meaningful change
- Include story ID in each entry
- Most recent entry at top
- Remove completed TODOs after next sprint

---

## 12. Test-Driven Development (TDD) Mandate

### TDD Classification

| Category | TDD Mandate | Test Strategy |
|----------|-------------|---------------|
| Domain Models | **Required** | Unit tests, property-based |
| Modbus Poller | **Required** | Mock pymodbus client |
| Normalizer | **Required** | Pure function tests with fixture data |
| SQLite Spool | **Required** | In-memory SQLite |
| Batch Uploader | **Required** | Mock httpx, test backoff |
| Ingestion Worker | **Required** | Mock DB session |
| API Endpoints | **Required** | TestClient with mocked DB |
| Configuration | Recommended | Unit tests |
| Utilities | Recommended | Unit tests |
| Documentation | N/A | - |

### TDD Without Manual Inspection

**CONSTRAINT**: Tests MUST NOT require manual interaction or visual inspection.

**Allowed Test Strategies**:
1. **Schema validation**: Output conforms to expected types and constraints
2. **Sanity checks**: Values in reasonable ranges
3. **Mock-based**: Mock external dependencies (Modbus, HTTP)
4. **Property-based**: Mathematical/logical properties hold (e.g., power balance)
5. **Fixture-based**: Test against known Modbus register response data

### TDD Workflow (Red-Green-Refactor)

1. **RED**: Write failing test first
   - Create test file before implementation file
   - Tests verify expected behavior against mocks
   - All tests must fail initially

2. **GREEN**: Write minimal code to pass
   - Only write enough code to make tests pass
   - No premature optimization

3. **REFACTOR**: Clean up while keeping tests green
   - Improve code quality
   - Tests must remain passing

---

## 13. Security Directives (Mandatory)

**Skill**: Security Guidelines (installed at `SKILL.md`)

The `SKILL.md` file contains security guidelines. It is **automatically loaded** and must be followed for all code changes.

All code must be written from a **security-first perspective**.

### 13.1 Security Review Checklist (Per Code Change)

Before any code is merged, verify:

- [ ] No hardcoded IP addresses, API URLs, or credentials
- [ ] No Secret Key Exposure (no API keys, tokens, or secrets in code or assets)
- [ ] No Path Traversal (validate and sanitize file paths)
- [ ] No Insecure Network Requests (HTTPS for VPS; local LAN Modbus TCP acceptable)
- [ ] No unvalidated user input used in network requests or queries
- [ ] No sensitive data logged in production
- [ ] No insecure data storage (sensitive data encrypted at rest)

### 13.2 IoT/Edge-Specific Security

- [ ] No plaintext credentials in config files (use environment variables)
- [ ] Modbus TCP connections restricted to local LAN only
- [ ] Input validation on all Modbus register values (range checks, type checks)
- [ ] SQL injection prevention in SQLite buffer queries (parameterized queries only)
- [ ] HTTPS validated at startup for VPS uplink URL (reject http://)
- [ ] TLS certificate verification always enabled for VPS connections

### 13.3 Input Validation (Hard Rules)

All external input must be validated:

| Input Source | Validation Required |
|--------------|---------------------|
| Sungrow Modbus registers | Type, range, valid register addresses, error responses |
| VPS ingest payloads | Schema validation, device_id match, payload size limits |
| API query parameters | Type, range, allowlist |
| Configuration (env vars) | Type validation, range checks, URL scheme validation |

### 13.4 Security in Definition of Done

Work is NOT Done if:
- Any item in Security Checklist fails
- Security tests not included for sensitive operations
- Input validation missing for external data
- Hardcoded secrets or URLs found in code
- TLS not enforced for internet-facing connections

---

## 14. Development Commands

```bash
# Lint (required before commit — zero warnings)
ruff check edge/src/ vps/src/

# Format (required before commit)
ruff format --check edge/src/ vps/src/

# Test (all tests must pass)
pytest edge/tests/ vps/tests/

# Test with coverage
pytest edge/tests/ vps/tests/ --cov=edge/src --cov=vps/src --cov-report=term-missing

# Type checking
mypy edge/src/ vps/src/

# Clean
rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
```

---

## 15. Project-Specific Rules

### Hard Constraints

### HC-001: No Data Loss
**Constraint**: Every polled Modbus reading must eventually reach TimescaleDB, even across network outages and process restarts.
**Rationale**: Solar/battery telemetry gaps create blind spots in energy analysis.
**Implications**:
- SQLite spool persists readings before upload
- Readings deleted only after VPS acknowledgment
- Retry with exponential backoff on upload failure
**Allowed**: Temporary delays in data delivery
**Forbidden**: Dropping readings silently, deleting unacknowledged data

### HC-002: Idempotent Ingestion
**Constraint**: Composite key `(device_id, ts)` is the dedup key. Use `INSERT ON CONFLICT DO NOTHING`.
**Rationale**: Batch replay after failure must not create duplicates.
**Implications**:
- Same batch can be sent multiple times safely
- VPS returns count of actually inserted rows
**Allowed**: Re-sending acknowledged batches
**Forbidden**: Upsert/overwrite semantics on duplicate keys

### HC-003: HTTPS Only for VPS Communication
**Constraint**: All edge-to-VPS traffic must use HTTPS with valid TLS certificates.
**Rationale**: Energy data transits the public internet.
**Implications**:
- Config validation rejects http:// VPS URLs at startup
- TLS certificate verification always enabled
**Allowed**: TLS 1.2+ with certificate verification
**Forbidden**: Plaintext HTTP to VPS, disabling certificate verification

### HC-004: WiNet-S Stability
**Constraint**: Modbus polling must respect WiNet-S hardware limitations.
**Rationale**: The WiNet-S dongle has limited processing power and can become unresponsive.
**Implications**:
- Minimum 5s between poll cycles
- 20ms delay between individual register reads within a cycle
- Exponential backoff on connection failures
**Allowed**: Configurable poll interval (minimum 5s)
**Forbidden**: Sub-5s polling, burst register reads without delay

### Domain-Specific Rules
- All pipeline components must be idempotent
- Poll rate and register delays must be configurable via environment variables
- Edge service must handle Modbus connection failures gracefully (log, backoff, reconnect)
- SQLite spool must survive unclean shutdowns (WAL mode)
- Modbus register map must be maintained in a single source file (`edge/src/registers.py`)
