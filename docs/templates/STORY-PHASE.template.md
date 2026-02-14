# Phase {{PHASE_NUMBER}}: {{PHASE_NAME}}

<!-- TEMPLATE: This file contains the detailed stories for one phase. -->
<!-- TEMPLATE: It supplements the story summaries in BACKLOG.md with full detail. -->
<!-- TEMPLATE: Replace all {{PLACEHOLDER}} values with project-specific content. -->
<!-- TEMPLATE: Remove all lines starting with "<!-- TEMPLATE:" before use. -->

<!-- TEMPLATE: The stories here must match the <story> entries in BACKLOG.md. -->
<!-- TEMPLATE: BACKLOG.md is the source of truth for status; this file has the full detail. -->

**Status**: Not Started | In Progress | Complete
**Stories**: {{STORY_COUNT}}
**Completed**: 0
**Depends On**: {{PHASE_DEPENDENCIES}}

---

## Phase Completion Criteria

This phase is complete when:
- [ ] All stories have status "done"
- [ ] All tests passing (`{{TEST_COMMAND}}`)
- [ ] Lint clean (`{{LINT_COMMAND}}`)
- [ ] Documentation updated
- [ ] {{PHASE_SPECIFIC_CRITERION}}

---

## Stories

<!-- TEMPLATE: Two story formats are provided below: -->
<!-- TEMPLATE: 1. Full Story — for TDD-mandated or complex stories -->
<!-- TEMPLATE: 2. Minimal Story — for simple or non-TDD stories -->
<!-- TEMPLATE: Use the format that matches the story's complexity -->

<!-- ============================================================ -->
<!-- FULL STORY FORMAT (for TDD-required or complex stories)       -->
<!-- ============================================================ -->

<!-- TEMPLATE: The XML structure matches BACKLOG.md for consistency. -->
<!-- TEMPLATE: The Coding Agent loads THIS file when implementing a story. -->

<story id="STORY-{{NUMBER}}" status="pending" complexity="{{S|M|L|XL}}" tdd="required">
  <title>{{STORY_TITLE}}</title>
  <dependencies>{{STORY_DEPENDENCIES}}</dependencies>

  <description>
    {{DETAILED_STORY_DESCRIPTION}}

    <!-- TEMPLATE: Include context, motivation, and domain knowledge here. -->
    <!-- TEMPLATE: The Coding Agent reads this to understand WHY, not just WHAT. -->
  </description>

  <!-- TEMPLATE: Reference applicable Design Principles from Architecture.md -->
  <!-- TEMPLATE: Remove this element for non-UI stories -->
  <design_intent>{{DP-XXX}}, {{DP-YYY}} — {{brief explanation of how principles apply}}</design_intent>

  <acceptance_criteria>
    <ac id="AC1">{{SPECIFIC_TESTABLE_CRITERION}}</ac>
    <ac id="AC2">{{SPECIFIC_TESTABLE_CRITERION}}</ac>
    <ac id="AC3">{{SPECIFIC_TESTABLE_CRITERION}}</ac>
    <ac id="AC4">{{SPECIFIC_TESTABLE_CRITERION}}</ac>
  </acceptance_criteria>

  <allowed_scope>
    <!-- TEMPLATE: Explicitly list ALL files that may be created or modified -->
    <!-- TEMPLATE: The Coding Agent is forbidden from touching files not listed here -->
    <file>{{SOURCE_DIR}}/{{PATH}}/{{FILE}}.{{EXT}}</file>
    <file>{{SOURCE_DIR}}/{{PATH}}/{{FILE}}.{{EXT}}</file>
    <file>{{TEST_DIR}}/{{PATH}}/{{FILE}}.{{EXT}}</file>
    <file>{{TEST_DIR}}/{{PATH}}/{{FILE}}.{{EXT}}</file>
    <file>{{TEST_DIR}}/fixtures/{{FIXTURE_FILE}}</file>
  </allowed_scope>

  <test_first>
    <!-- TEMPLATE: Required when tdd="required" -->
    <!-- TEMPLATE: This section defines what tests must exist BEFORE implementation -->
    <item>Create {{TEST_DIR}}/{{TEST_FILE}} FIRST</item>
    <item>Create {{TEST_DIR}}/{{TEST_FILE_2}} FIRST</item>
    <item>{{MOCK_SETUP_INSTRUCTION}}</item>
    <item>Test: {{EXPECTED_BEHAVIOR_1}}</item>
    <item>Test: {{EXPECTED_BEHAVIOR_2}}</item>
    <item>Test: {{ERROR_CASE}}</item>
    <item>Test: {{EDGE_CASE}}</item>
  </test_first>

  <test_plan>
    - Unit tests for {{COMPONENT}} with mocked {{DEPENDENCY}}
    - Unit tests for {{MODEL}} (construction, validation, serialization)
    - Tests against fixture data
    - {{ADDITIONAL_TEST_STRATEGY}}
    - `{{TEST_COMMAND}}` all pass
  </test_plan>

  <notes>
    - {{IMPLEMENTATION_HINT}}
    - {{ADR_REFERENCE}}
    - {{DOMAIN_KNOWLEDGE}}
  </notes>
</story>

---

<!-- ============================================================ -->
<!-- MINIMAL STORY FORMAT (for simple or non-TDD stories)          -->
<!-- ============================================================ -->

<story id="STORY-{{NUMBER}}" status="pending" complexity="{{S|M|L|XL}}" tdd="recommended">
  <title>{{STORY_TITLE}}</title>
  <dependencies>{{STORY_DEPENDENCIES}}</dependencies>

  <description>
    {{BRIEF_STORY_DESCRIPTION}}
  </description>

  <acceptance_criteria>
    <ac id="AC1">{{CRITERION_1}}</ac>
    <ac id="AC2">{{CRITERION_2}}</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>{{SOURCE_DIR}}/{{FILE}}.{{EXT}}</file>
    <file>{{TEST_DIR}}/{{TEST_FILE}}.{{EXT}}</file>
  </allowed_scope>

  <test_plan>
    - {{TEST_STRATEGY}}
    - `{{TEST_COMMAND}}` all pass
  </test_plan>

  <notes>
    - {{NOTE}}
  </notes>
</story>

---

<!-- TEMPLATE: Continue adding stories for this phase -->
<!-- TEMPLATE: Use full format for TDD-required or complex stories -->
<!-- TEMPLATE: Use minimal format for simpler stories -->

---

## Phase Notes

<!-- TEMPLATE: Add phase-level context and considerations -->

### Dependencies on Other Phases
- Phase {{X}} must be complete for {{REASON}}

### Known Risks
- {{RISK_1}}: {{MITIGATION}}
- {{RISK_2}}: {{MITIGATION}}

### Technical Debt
- {{TECH_DEBT_ITEM}} — to be addressed in Phase {{X}}
