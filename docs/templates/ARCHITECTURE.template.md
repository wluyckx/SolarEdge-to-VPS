# Architecture.md - {{PROJECT_NAME}}

**Last Updated**: {{DATE}}

---

## Overview

<!-- TEMPLATE: Replace with your project description -->
<!-- TEMPLATE: If this project has a companion service, add a Companion Project line below -->

{{PROJECT_DESCRIPTION}}

**Primary Goal**: {{PRIMARY_GOAL}}

**Companion Project**: {{COMPANION_PROJECT_DESCRIPTION}}
<!-- TEMPLATE: Example: "This app is a client of the [My-API](../My-API/), which provides data and calculation endpoints." -->
<!-- TEMPLATE: Remove the Companion Project line if not applicable -->

---

## Tech Stack

<!-- TEMPLATE: Replace with your actual technologies -->
<!-- TEMPLATE: Be exhaustive — the Coding Agent cannot use packages not listed here -->

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | {{LANGUAGE}} | {{VERSION}} | {{PURPOSE}} |
| Framework | {{FRAMEWORK}} | {{VERSION}} | {{PURPOSE}} |
| Database | {{DATABASE}} | {{VERSION}} | {{PURPOSE}} |
| HTTP Client | {{HTTP_CLIENT}} | {{VERSION}} | {{PURPOSE}} |
| State Management | {{STATE_MANAGEMENT}} | {{VERSION}} | {{PURPOSE}} |
| Testing | {{TEST_FRAMEWORK}} | latest | {{PURPOSE}} |
| Mock Framework | {{MOCK_FRAMEWORK}} | latest | {{PURPOSE}} |
| Linting | {{LINTER}} | latest | {{PURPOSE}} |
| Formatting | {{FORMATTER}} | latest | {{PURPOSE}} |

### Dependencies NOT in Tech Stack (Forbidden Without ADR)
Any package not listed above requires an Architecture Proposal before use.

---

## Directory Structure

<!-- TEMPLATE: Replace with your project structure -->
<!-- TEMPLATE: This is the source of truth for where files go — the Coding Agent must match it -->

```
{{PROJECT_NAME}}/
├── CLAUDE.md                        # Agent workflow rules
├── Architecture.md                  # This file
├── docs/
│   ├── BACKLOG.md                   # Stories and requirements
│   └── stories/                     # Detailed story files per phase
│       ├── phase-1-{{PHASE_NAME}}.md
│       └── phase-2-{{PHASE_NAME}}.md
├── {{SOURCE_DIR}}/
│   ├── {{ENTRY_POINT}}              # App / service entry point
│   ├── core/                        # Shared infrastructure
│   │   ├── constants/
│   │   │   └── {{CONSTANTS_FILE}}   # Timeouts, defaults, intervals
│   │   ├── errors/
│   │   │   └── {{ERRORS_FILE}}      # Error / failure types
│   │   ├── network/
│   │   │   ├── {{API_CLIENT_FILE}}  # External API client
│   │   │   └── api_key_service.{{EXT}}  # API key lifecycle (request, store, inject)
│   │   └── storage/
│   │       └── {{STORAGE_FILE}}     # Database / cache definition
│   ├── features/                    # Feature modules
│   │   └── {{FEATURE_NAME}}/
│   │       ├── data/                # Repository implementations, services
│   │       ├── domain/              # Models, repository interfaces
│   │       │   ├── models/
│   │       │   └── repositories/
│   │       └── presentation/        # UI, state management
│   │           ├── providers/       # State management
│   │           ├── screens/         # Screen / page widgets
│   │           └── widgets/         # Reusable UI components
│   └── shared/                      # Cross-feature shared code
│       └── {{SHARED_FILES}}
├── {{TEST_DIR}}/
│   ├── features/                    # Mirrors source features
│   ├── core/
│   ├── fixtures/                    # Mock data / test fixtures
│   │   └── {{FIXTURE_DIR}}/
│   └── helpers/
│       └── {{TEST_HELPERS_FILE}}
└── {{CONFIG_FILE}}                  # Dependencies / configuration
```

<!-- TEMPLATE: The api_key_service entry is an example — include it if your project manages -->
<!-- API keys or authentication tokens. Remove if not applicable. -->

---

## Key Components

<!-- TEMPLATE: Document your key components -->
<!-- TEMPLATE: Each component should have: Location, Responsibility, Protocol/Pattern, Dependencies -->

### 1. {{COMPONENT_NAME}}
- **Location**: `{{SOURCE_DIR}}/{{PATH}}/`
- **Responsibility**: {{WHAT_IT_DOES}}
- **Protocol**: {{HOW_IT_COMMUNICATES}}
- **Dependencies**: {{PACKAGES_OR_COMPONENTS}}

### 2. {{COMPONENT_NAME}}
- **Location**: `{{SOURCE_DIR}}/{{PATH}}/`
- **Responsibility**: {{WHAT_IT_DOES}}
- **Dependencies**: {{PACKAGES_OR_COMPONENTS}}

### 3. {{COMPONENT_NAME}}
- **Location**: `{{SOURCE_DIR}}/{{PATH}}/`
- **Responsibility**: {{WHAT_IT_DOES}}
- **Dependencies**: {{PACKAGES_OR_COMPONENTS}}

---

## Data Flow

<!-- TEMPLATE: Replace with your system's data flow diagram -->
<!-- TEMPLATE: Show how data moves between layers and external systems -->

```
┌─────────────────────────────────────────────────────┐
│                   {{PROJECT_NAME}}                     │
│                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────┐│
│  │ Presentation │   │    Domain    │   │   Data   ││
│  │  (UI, State) │──>│  (Models,   │<──│(Services,││
│  │              │   │  Repo IFs)  │   │  Repos)  ││
│  └──────────────┘   └──────────────┘   └────┬─────┘│
│                                              │      │
└──────────────────────────────────────────────┼──────┘
                                               │
                   ┌───────────────────────────┼───────────┐
                   │                           │           │
                   ▼                           ▼           ▼
          ┌──────────────┐          ┌──────────────┐ ┌──────────┐
          │ {{SOURCE_1}} │          │ {{SOURCE_2}} │ │  Local   │
          │ {{PROTOCOL}} │          │ {{PROTOCOL}} │ │  Storage │
          └──────────────┘          └──────────────┘ └──────────┘
```

<!-- TEMPLATE: Add named flow descriptions for each major data path -->
<!-- TEMPLATE: Each flow should describe the step-by-step journey of data -->

### Flow: {{FLOW_NAME_1}}
1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}
4. {{STEP_4}}

### Flow: {{FLOW_NAME_2}}
1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}

### Flow: {{FLOW_NAME_3}} (Offline / Fallback)
1. {{STEP_1}} — cache-first strategy
2. {{STEP_2}} — fallback when external source unavailable
3. {{STEP_3}} — clearly indicate data freshness to user

### Flow Characteristics
- **Reactive**: {{HOW_UI_UPDATES}}
- **Offline-first**: {{OFFLINE_STRATEGY}}
- **Configurable**: {{WHAT_IS_CONFIGURABLE}}
- **Resilient**: {{HOW_ERRORS_ARE_HANDLED}}

---

## Design Decisions

<!-- TEMPLATE: Summarize key design decisions in table form -->
<!-- TEMPLATE: These are the short-form summaries; ADRs at bottom have the full rationale -->

| Decision | Choice | Rationale |
|----------|--------|-----------|
| {{DECISION_1}} | {{CHOICE}} | {{RATIONALE}} |
| {{DECISION_2}} | {{CHOICE}} | {{RATIONALE}} |
| {{DECISION_3}} | {{CHOICE}} | {{RATIONALE}} |

---

## Design Principles

<!-- TEMPLATE: Design Principles guide the "feel" of the project output — they prevent -->
<!-- generic, unfocused results. They are guardrails, not a design system. -->
<!-- TEMPLATE: Remove this section if your project has no user-facing output. -->
<!-- TEMPLATE: Specific tokens and patterns emerge during implementation and should be -->
<!-- captured in the agent memory topic file `design.md`, not here. -->

These principles guide all output decisions. They are not a design system — they are guardrails
that prevent generic output and ensure the product feels intentional. Specific patterns, tokens,
and implementation decisions are captured iteratively in the agent memory topic file `design.md`
as work progresses.

### DP-001: {{PRINCIPLE_NAME}}
{{PRINCIPLE_DESCRIPTION}}
<!-- TEMPLATE: Example: "Numbers First — The primary content of this app is numerical. -->
<!-- The key number on any screen must be the largest, most prominent element." -->

### DP-002: {{PRINCIPLE_NAME}}
{{PRINCIPLE_DESCRIPTION}}
<!-- TEMPLATE: Example: "Honest About Data Freshness — Always distinguish live data from -->
<!-- cached or estimated values. Never display a number without indicating its source." -->

<!-- TEMPLATE: Add more principles as needed. Common categories: -->
<!-- - Information hierarchy (what is most important?) -->
<!-- - Data trustworthiness (how to show confidence/freshness?) -->
<!-- - Interaction model (dashboard vs feed vs wizard?) -->
<!-- - Tone and language (formal vs casual? domain-specific?) -->
<!-- - Accessibility (color independence, screen reader support?) -->

---

## Integration Points

### Inputs

<!-- TEMPLATE: Document all external data sources -->

- **{{SOURCE_NAME}}**:
  - Protocol: {{PROTOCOL}}
  - Endpoint: {{ENDPOINT}}
  - Auth: {{AUTH_METHOD}}
  - Data: {{WHAT_DATA}}

- **{{SOURCE_NAME}}**:
  - Protocol: {{PROTOCOL}}
  - Auth: {{AUTH_METHOD}}

### Outputs

- **{{OUTPUT_NAME}}**: {{DESCRIPTION}}
- **{{OUTPUT_NAME}}**: {{DESCRIPTION}}

---

## Development Patterns

<!-- TEMPLATE: Document patterns the Coding Agent must follow -->
<!-- TEMPLATE: Use {{LANGUAGE}} code examples that match your tech stack -->

### {{PATTERN_NAME}} Pattern

```{{LANGUAGE_ID}}
// Example code in {{LANGUAGE}}
{{CODE_EXAMPLE}}
```

### Error Handling
- {{ERROR_PATTERN_1}}
- {{ERROR_PATTERN_2}}
- {{ERROR_PATTERN_3}}

### Configuration
- Use `{{CONFIG_LOCATION}}` for compile-time defaults
- Use {{RUNTIME_CONFIG}} for user-configurable runtime settings
- No hardcoded IPs, URLs, or secrets in code
- Environment-specific config via {{ENV_STRATEGY}}

---

## Development Workflow

```bash
# Setup
{{SETUP_COMMAND}}

# Lint (must pass with zero warnings)
{{LINT_COMMAND}}

# Format (must pass)
{{FORMAT_COMMAND}}

# Test
{{TEST_COMMAND}}

# Test with coverage report
{{COVERAGE_COMMAND}}

# Code generation (if applicable)
{{CODEGEN_COMMAND}}

# Run
{{RUN_COMMAND}}

# Clean rebuild
{{CLEAN_COMMAND}}
```

---

## Testing Strategy

| Test Type | Location | Coverage Target | Tools |
|-----------|----------|-----------------|-------|
| Unit Tests | `{{TEST_DIR}}/{{UNIT_PATH}}/` | {{TARGET}}% | {{TOOLS}} |
| Integration | `{{TEST_DIR}}/{{INT_PATH}}/` | Key flows | {{TOOLS}} |
| Fixtures | `{{TEST_DIR}}/fixtures/` | Mock data | {{FORMAT}} |

### Test Requirements
- {{TEST_REQUIREMENT_1}}
- {{TEST_REQUIREMENT_2}}
- {{TEST_REQUIREMENT_3}}
- No tests may depend on real network access or real external services

### Mock Strategy
- {{MOCK_STRATEGY_1}}
- {{MOCK_STRATEGY_2}}

### Time-Dependent Testing

<!-- TEMPLATE: If your project has time-sensitive features (polling, scheduling, TTL, -->
<!-- cron-like triggers, rate limiting), document the test strategy here. -->
<!-- TEMPLATE: Remove this section if not applicable. -->

Several features depend on clock time. All time-dependent code must accept an injectable
clock (or time provider) to enable deterministic testing:

| Feature | Time Dependency | Test Strategy |
|---------|----------------|---------------|
| {{FEATURE}} | {{DEPENDENCY}} | {{STRATEGY}} |
| {{FEATURE}} | {{DEPENDENCY}} | {{STRATEGY}} |

**Pattern**: Use a clock abstraction injected via {{INJECTION_METHOD}}. Tests override with
a fixed or advancing clock. Never call the system clock directly in business logic.

---

## Environment & Secrets

| Variable | Purpose | Storage | Required |
|----------|---------|---------|----------|
| `{{VAR_NAME}}` | {{PURPOSE}} | {{WHERE_STORED}} | Yes/No |

**Security**: All secrets via secure storage or environment variables, never in code.

---

## Operational Assumptions

1. **Runtime**: {{RUNTIME_REQUIREMENTS}}
2. **Storage**: {{STORAGE_REQUIREMENTS}}
3. **Memory**: {{MEMORY_REQUIREMENTS}}
4. **Network**: {{NETWORK_REQUIREMENTS}}

---

## Hard Constraints

<!-- TEMPLATE: Define non-negotiable project constraints -->
<!-- TEMPLATE: These are referenced from BACKLOG.md and stories -->

### HC-001: {{CONSTRAINT_NAME}}
**Constraint**: {{CONSTRAINT_DESCRIPTION}}

**Rationale**: {{RATIONALE}}

**Implications**:
- {{IMPLICATION_1}}
- {{IMPLICATION_2}}

**Allowed**: {{ALLOWED}}
**Forbidden**: {{FORBIDDEN}}

### HC-002: {{CONSTRAINT_NAME}}
**Constraint**: {{CONSTRAINT_DESCRIPTION}}

**Rationale**: {{RATIONALE}}

**Implications**:
- {{IMPLICATION_1}}

**Allowed**: {{ALLOWED}}
**Forbidden**: {{FORBIDDEN}}

---

## Architecture Decision Records (ADRs)

<!-- TEMPLATE: Add ADRs as you make architectural decisions -->

### ADR-001: {{DECISION_TITLE}}
**Status**: Proposed | Approved | Deprecated | Superseded
**Date**: {{DATE}}
**Stories**: STORY-XXX, STORY-YYY

**Context**:
{{CONTEXT_DESCRIPTION}}

**Decision**:
{{DECISION_DESCRIPTION}}

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| {{OPTION_1}} | {{PROS}} | {{CONS}} |
| {{OPTION_2}} | {{PROS}} | {{CONS}} |

**Rationale**:
- {{RATIONALE_1}}
- {{RATIONALE_2}}

**Consequences**:
- {{CONSEQUENCE_1}}
- {{CONSEQUENCE_2}}

---

### ADR-002: {{DECISION_TITLE}}
<!-- Copy ADR template above for additional decisions -->

---

## Deployment Strategy

<!-- TEMPLATE: Document deployment approach -->

### Environments

| Environment | URL | Purpose |
|-------------|-----|---------|
| Development | localhost | Local development |
| Staging | {{STAGING_URL}} | Testing |
| Production | {{PRODUCTION_URL}} | Live |

### Deployment Method

<!-- TEMPLATE: Document your deployment method (Docker, app store, CI/CD, etc.) -->

{{DEPLOYMENT_DESCRIPTION}}

---

## Documentation Strategy

<!-- TEMPLATE: Document how documentation is maintained -->

### Documentation Sources
| Source | Location | Auto-generated |
|--------|----------|----------------|
| Architecture | `Architecture.md` | No |
| Technical Design | `technicaldesign.md` (optional) | No |
| Backlog | `docs/BACKLOG.md` | No |
| Stories | `docs/stories/*.md` | No |
| Code docs | {{CODE_DOC_TOOL}} | Yes |

<!-- TEMPLATE: Mark technicaldesign.md as applicable or remove if not used -->

### Documentation Requirements
- All public APIs must have documentation comments
- ADRs for all significant architectural decisions
- Story files for all development work
- CHANGELOG headers in all modified source files

---

## Related Documents

- `CLAUDE.md`: Agent workflow rules and gates (highest authority)
- `docs/BACKLOG.md`: Stories, acceptance criteria, progress tracking
- `SKILL.md`: Security guidelines
- `technicaldesign.md`: Detailed schemas, specifications (optional — use when Architecture.md needs supplementary detail)
