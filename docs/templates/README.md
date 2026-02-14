# Governance Templates

Reusable project governance templates for AI-assisted development with Claude Code.

These templates provide a structured framework for managing projects where Claude Code agents
handle both governance (planning, story definition, architecture) and implementation (coding,
testing, debugging). They enforce clear boundaries, traceability, and session continuity.

## Quick Start

1. Copy templates to your project root
2. Replace all `{{PLACEHOLDER}}` values with project-specific content
3. Remove template comments (lines starting with `<!-- TEMPLATE:`)
4. Customize sections as needed

## Template Files

| Template | Purpose | Copy To | Required |
|----------|---------|---------|----------|
| `CLAUDE.template.md` | Agent operating rules and gates | `CLAUDE.md` | Yes |
| `ARCHITECTURE.template.md` | Technical architecture, ADRs, design principles | `Architecture.md` | Yes |
| `BACKLOG.template.md` | Story backlog in XML format | `docs/BACKLOG.md` | Yes |
| `STORY-PHASE.template.md` | Phase/epic story grouping with full and minimal formats | `docs/stories/phase-X.md` | Yes |
| `MEMORY.template.md` | Agent memory for session continuity | `{{MEMORY_PATH}}/memory/MEMORY.md` | Yes |
| `TECHNICALDESIGN.template.md` | Detailed schemas, APIs, validation (optional) | `technicaldesign.md` | No |
| `SKILL.md` | VibeSec security guidelines | `SKILL.md` | Recommended |

## Placeholders Reference

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{{PROJECT_NAME}}` | Project name | "My Energy App" |
| `{{PROJECT_DESCRIPTION}}` | One-line description | "Mobile app for energy monitoring" |
| `{{PRIMARY_GOAL}}` | What the project achieves | "Real-time cost visibility" |
| `{{LANGUAGE}}` | Primary programming language | "Dart", "Python", "TypeScript" |
| `{{FRAMEWORK}}` | Primary framework | "Flutter", "FastAPI", "Next.js" |
| `{{DATABASE}}` | Database technology | "SQLite", "PostgreSQL" |
| `{{SOURCE_DIR}}` | Source code directory | "lib", "src", "app" |
| `{{TEST_DIR}}` | Test directory | "test", "tests", "__tests__" |
| `{{EXT}}` | File extension | "dart", "py", "ts" |
| `{{LINT_COMMAND}}` | Lint command | "flutter analyze", "ruff check src/" |
| `{{FORMAT_COMMAND}}` | Format command | "dart format --set-exit-if-changed .", "black ." |
| `{{TEST_COMMAND}}` | Test command | "flutter test", "pytest tests/" |
| `{{COVERAGE_COMMAND}}` | Coverage command | "flutter test --coverage", "pytest --cov" |
| `{{BUILD_COMMAND}}` | Build command | "flutter build apk", "docker build ." |
| `{{CODEGEN_COMMAND}}` | Code generation command | "dart run build_runner build" |
| `{{CLEAN_COMMAND}}` | Clean command | "flutter clean && flutter pub get" |
| `{{MEMORY_PATH}}` | Claude memory directory path | ".claude/projects/-Users-Name-Project" |
| `{{PRODUCTION_URL}}` | Production deployment URL | "api.example.com" |
| `{{COMPANION_PROJECT_DESCRIPTION}}` | Related project reference | "Client of the [My-API](../My-API/)" |

## Customization Guide

### CLAUDE.md
- Adjust agent responsibility model for your team structure
- Uncomment one of the code documentation header options (Dart, Python, or TypeScript)
- Add/remove response modes as needed
- Customize security directives for your domain (mobile, web, API)
- Add project-specific block reasons and hard constraints
- Fill in development commands with your actual lint/test/build commands
- Configure `technicaldesign.md` in the precedence hierarchy if used

### Architecture.md
- Replace tech stack with your actual technologies
- Add a Companion Project reference if applicable
- Add Design Principles section with project-specific guardrails
- Document multiple named data flows (not just one generic diagram)
- Add Time-Dependent Testing guidance if your project has time-sensitive features
- Add ADRs as architectural decisions are made
- Mark `technicaldesign.md` as optional in Related Documents
- Include `api_key_service` in directory structure if your project manages API keys

### BACKLOG.md (XML format)
- The backlog uses XML format for structured, machine-parseable story data
- Define MVP scope, constraints, and DoR/DoD
- Add `<design_intent>` to stories with user-facing output
- Use `<test_first>` for TDD-mandated stories
- Maintain the dependency graph in ASCII art
- Update `<metadata>` changelog when restructuring

### Story Phases
- Create one file per phase/epic
- Use "full story" format for TDD-required or complex stories
- Use "minimal story" format for simpler stories
- Match the XML structure used in BACKLOG.md
- Include `<design_intent>` for UI stories referencing Architecture.md Design Principles

### MEMORY.md
- Keep under 200 lines (hard platform limit)
- Structure as a concise index, not a log
- Link to topic files for detailed reference material
- Always include a Resume Checklist with exact commands
- Update at end of every governance session

### Technical Design (optional)
- Use only when Architecture.md needs supplementary detail
- Good for: detailed data model schemas, API endpoint specs, validation rules, DB schemas
- Not needed for: simple projects where Architecture.md covers everything
- Replace language-specific examples with your project's language

## What We Learned

These templates evolved significantly during real project use. Here is what changed and why:

### XML format for backlogs
The original BACKLOG.template.md used Markdown tables. In practice, structured data (stories
with status, complexity, dependencies, acceptance criteria) is much better represented in XML.
It is easier to parse, update programmatically, and validate. The agent can reliably find and
modify specific story attributes without ambiguity.

### Session Continuity is critical
Agent context windows close. Without MEMORY.md, every new session starts from scratch --
the agent re-reads Architecture.md, re-discovers project state, and repeats analysis it
already did. The MEMORY.template.md captures the pattern that prevents this: a concise
index of current state, key decisions, and exact resume commands.

### Design Principles prevent generic output
Without explicit design principles in Architecture.md, the agent produces generic, unfocused
UI and output. Design Principles (DP-001, DP-002, etc.) are guardrails that encode the
project's visual and interaction philosophy. They are not a design system -- they are
constraints that prevent the agent from defaulting to "standard Material Design" when the
project needs something more intentional.

### Companion Projects need explicit linkage
Projects that consume or are consumed by other services need an explicit reference in
Architecture.md. Without it, the agent makes assumptions about API contracts, capabilities,
and authentication that may be wrong.

### Time-dependent testing needs a strategy
Any project with polling, caching TTLs, scheduling, or time-based boundaries needs an
explicit testing strategy for time-dependent code. The pattern is always the same: inject a
clock abstraction, never call the system clock directly in business logic.

### technicaldesign.md should be optional
Not every project needs a separate technical design document. Architecture.md covers most
needs. The technical design file is valuable when you have complex database schemas, detailed
API specifications, or intricate validation rules that would clutter Architecture.md.

## Best Practices

1. **Keep CLAUDE.md strict** -- It is the source of truth for agent behavior
2. **Document all ADRs** -- Every significant decision gets an ADR in Architecture.md
3. **Use Allowed Scope** -- Every story explicitly lists permitted file changes
4. **TDD where applicable** -- Define test strategy per story category
5. **No manual inspection** -- Automate validation wherever possible
6. **Design Principles over design systems** -- Guardrails, not specifications
7. **Memory is a guide, not gospel** -- Git log and test results are ground truth
8. **XML for structured data** -- Backlogs and stories use XML for reliability
9. **200-line memory limit** -- Keep MEMORY.md concise, use topic files for detail
10. **Mark optional documents** -- Not every project needs technicaldesign.md
