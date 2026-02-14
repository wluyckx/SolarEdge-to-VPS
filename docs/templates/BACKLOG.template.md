<backlog>

<!-- TEMPLATE: This backlog uses XML format for structured data. -->
<!-- TEMPLATE: Replace all {{PLACEHOLDER}} values with project-specific content. -->
<!-- TEMPLATE: Remove all lines starting with "<!-- TEMPLATE:" before use. -->

<metadata>
  <project>{{PROJECT_NAME}}</project>
  <last_updated>{{DATE}}</last_updated>
  <total_stories>{{TOTAL_STORIES}}</total_stories>
  <done>0</done>
  <progress>0%</progress>
  <changelog>
    <entry date="{{DATE}}">Initial backlog creation ({{TOTAL_STORIES}} stories across {{PHASE_COUNT}} phases)</entry>
  </changelog>
</metadata>

<!-- ============================================================ -->
<!-- MVP DEFINITION                                                -->
<!-- ============================================================ -->

<mvp>
  <goal>{{MVP_GOAL_DESCRIPTION}}</goal>

  <scope>
    <!-- TEMPLATE: List MVP features in priority order with story references -->
    <item priority="1" story="STORY-001">{{FEATURE_1}}</item>
    <item priority="2" story="STORY-002">{{FEATURE_2}}</item>
    <item priority="3" story="STORY-003">{{FEATURE_3}}</item>
    <item priority="4" story="STORY-004">{{FEATURE_4}}</item>
  </scope>

  <deliverables>
    <item>{{DELIVERABLE_1}}</item>
    <item>{{DELIVERABLE_2}}</item>
    <item>{{DELIVERABLE_3}}</item>
  </deliverables>

  <post_mvp>
    <item>{{POST_MVP_FEATURE_1}}</item>
    <item>{{POST_MVP_FEATURE_2}}</item>
    <item>{{POST_MVP_FEATURE_3}}</item>
  </post_mvp>
</mvp>

<!-- ============================================================ -->
<!-- KEY CONSTRAINTS                                               -->
<!-- ============================================================ -->

<!-- TEMPLATE: Reference constraints defined in Architecture.md -->

<constraints>
  <constraint id="HC-001" ref="Architecture.md">{{CONSTRAINT_1_DESCRIPTION}}</constraint>
  <constraint id="HC-002" ref="Architecture.md">{{CONSTRAINT_2_DESCRIPTION}}</constraint>
</constraints>

<!-- ============================================================ -->
<!-- DEFINITION OF READY                                           -->
<!-- ============================================================ -->

<dor>
  <title>Definition of Ready</title>
  <description>A story is ready for development when ALL conditions are true:</description>
  <checklist>
    <item>Clear description of what needs to be built</item>
    <item>Acceptance criteria are specific and testable</item>
    <item>Dependencies are identified and completed</item>
    <item>Technical approach is understood</item>
    <item>Estimated complexity noted (S/M/L/XL)</item>
    <item>Allowed Scope defined (files/modules)</item>
    <item>Test-First Requirements defined (if TDD-mandated)</item>
    <item>Mock strategy defined for external dependencies</item>
    <!-- TEMPLATE: Add design intent item if your project has Design Principles: -->
    <item>Design intent noted for presentation stories (ref Architecture.md Design Principles)</item>
    <!-- TEMPLATE: Remove the design intent item if not applicable -->
  </checklist>
</dor>

<!-- ============================================================ -->
<!-- DEFINITION OF DONE                                            -->
<!-- ============================================================ -->

<dod>
  <title>Definition of Done</title>
  <description>A story is complete when ALL conditions are true:</description>
  <checklist>
    <item>All acceptance criteria pass</item>
    <item>{{LINT_COMMAND}} passes with zero warnings</item>
    <item>{{FORMAT_COMMAND}} check passes</item>
    <item>{{TEST_COMMAND}} passes with no failures</item>
    <item>Documentation on all public APIs</item>
    <item>CHANGELOG header updated in modified files</item>
    <item>No undocumented TODOs introduced</item>
    <item>Security checklist passed (per CLAUDE.md section 13)</item>
    <!-- TEMPLATE: Add if your project has Design Principles: -->
    <item>Design principles respected (per Architecture.md Design Principles)</item>
    <item>Code reviewed (self-review minimum)</item>
  </checklist>
</dod>

<!-- ============================================================ -->
<!-- STORY TEMPLATE                                                -->
<!-- ============================================================ -->

<!--
TEMPLATE: This is the canonical story format. Copy it for each story.

<story id="STORY-XXX" status="pending" complexity="S|M|L|XL" tdd="required|recommended|na">
  <title>Story Title</title>
  <dependencies>STORY-YYY, STORY-ZZZ | None</dependencies>
  <description>Brief description of what needs to be built and why.</description>
  <design_intent>DP-001, DP-003 — reference applicable Design Principles</design_intent>
  <acceptance_criteria>
    <ac id="AC1">Specific testable criterion</ac>
    <ac id="AC2">Another criterion</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>{{SOURCE_DIR}}/path/to/file.{{EXT}}</file>
    <file>{{TEST_DIR}}/path/to/test.{{EXT}}</file>
  </allowed_scope>
  <test_first>
    <item>Create test file FIRST</item>
    <item>Write tests for expected behavior</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>How to verify this works</test_plan>
  <notes>Implementation hints or decisions</notes>
</story>

TEMPLATE: The <design_intent> element is optional — use it for stories that produce
user-facing output. It references Design Principle IDs from Architecture.md.

TEMPLATE: The <test_first> element is required when tdd="required", optional otherwise.
-->

<!-- ============================================================ -->
<!-- PRIORITY ORDER                                                -->
<!-- ============================================================ -->

<priority_order>
  <tier name="Foundation" description="Core infrastructure required by everything else">
    <entry priority="1" story="STORY-001" title="{{TITLE}}" complexity="{{S|M|L|XL}}" deps="None" />
    <entry priority="2" story="STORY-002" title="{{TITLE}}" complexity="{{S|M|L|XL}}" deps="STORY-001" />
  </tier>

  <tier name="{{TIER_NAME}}" description="{{TIER_DESCRIPTION}}">
    <entry priority="3" story="STORY-003" title="{{TITLE}}" complexity="{{S|M|L|XL}}" deps="STORY-002" />
    <entry priority="4" story="STORY-004" title="{{TITLE}}" complexity="{{S|M|L|XL}}" deps="STORY-003" />
  </tier>

  <!-- TEMPLATE: Add more tiers as needed -->
  <!-- TEMPLATE: Tiers group stories by functional area, not by phase -->

  <tier name="{{TIER_NAME}}" description="{{TIER_DESCRIPTION}}">
    <entry priority="5" story="STORY-005" title="{{TITLE}}" complexity="{{S|M|L|XL}}" deps="STORY-004" />
  </tier>
</priority_order>

<!-- ============================================================ -->
<!-- PHASE 1: {{PHASE_NAME}}                                       -->
<!-- Story file: docs/stories/phase-1-{{PHASE_SLUG}}.md            -->
<!-- ============================================================ -->

<phase id="1" name="{{PHASE_NAME}}" story_file="docs/stories/phase-1-{{PHASE_SLUG}}.md">

<!-- TEMPLATE: Full story example -->

<story id="STORY-001" status="pending" complexity="M" tdd="recommended">
  <title>{{STORY_TITLE}}</title>
  <dependencies>None</dependencies>
  <description>
    {{STORY_DESCRIPTION}}
  </description>
  <acceptance_criteria>
    <ac id="AC1">{{ACCEPTANCE_CRITERION_1}}</ac>
    <ac id="AC2">{{ACCEPTANCE_CRITERION_2}}</ac>
    <ac id="AC3">{{ACCEPTANCE_CRITERION_3}}</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>{{SOURCE_DIR}}/{{FILE_1}}</file>
    <file>{{SOURCE_DIR}}/{{FILE_2}}</file>
    <file>{{TEST_DIR}}/{{TEST_FILE}}</file>
  </allowed_scope>
  <test_plan>
    - {{TEST_STEP_1}}
    - {{TEST_STEP_2}}
    - {{TEST_COMMAND}} all pass
  </test_plan>
  <notes>
    - {{NOTE_1}}
    - {{NOTE_2}}
  </notes>
</story>

<!-- TEMPLATE: Repeat <story> blocks for each story in this phase -->

<story id="STORY-002" status="pending" complexity="L" tdd="required">
  <title>{{STORY_TITLE}}</title>
  <dependencies>STORY-001</dependencies>
  <description>
    {{STORY_DESCRIPTION}}
  </description>
  <acceptance_criteria>
    <ac id="AC1">{{ACCEPTANCE_CRITERION_1}}</ac>
    <ac id="AC2">{{ACCEPTANCE_CRITERION_2}}</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>{{SOURCE_DIR}}/{{FILE_1}}</file>
    <file>{{TEST_DIR}}/{{TEST_FILE}}</file>
  </allowed_scope>
  <test_first>
    <item>Create {{TEST_DIR}}/{{TEST_FILE}} FIRST</item>
    <item>Write tests for {{EXPECTED_BEHAVIOR}}</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - {{TEST_STEP_1}}
    - {{TEST_COMMAND}} all pass
  </test_plan>
  <notes>
    - {{NOTE_1}}
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PHASE 2: {{PHASE_NAME}}                                       -->
<!-- Story file: docs/stories/phase-2-{{PHASE_SLUG}}.md            -->
<!-- ============================================================ -->

<phase id="2" name="{{PHASE_NAME}}" story_file="docs/stories/phase-2-{{PHASE_SLUG}}.md">

<!-- TEMPLATE: Add stories for phase 2 -->
<!-- TEMPLATE: Copy story blocks from phase 1 template -->

</phase>

<!-- TEMPLATE: Add more phases as needed -->

<!-- ============================================================ -->
<!-- PROGRESS OVERVIEW                                             -->
<!-- ============================================================ -->

<progress>
  <phase_summary>
    <phase id="1" name="{{PHASE_1_NAME}}" stories="{{COUNT}}" done="0" progress="0%" link="stories/phase-1-{{PHASE_SLUG}}.md" />
    <phase id="2" name="{{PHASE_2_NAME}}" stories="{{COUNT}}" done="0" progress="0%" link="stories/phase-2-{{PHASE_SLUG}}.md" />
  </phase_summary>
  <total stories="{{TOTAL_STORIES}}" done="0" progress="0%" />
</progress>

<!-- ============================================================ -->
<!-- DEPENDENCY GRAPH                                              -->
<!-- ============================================================ -->

<dependency_graph>
<!--
TEMPLATE: Visualize story dependencies in ASCII art format.
This makes it easy to see which stories can be parallelized.

STORY-001 ({{TITLE}})
├── STORY-002 ({{TITLE}})
│   ├── STORY-003 ({{TITLE}})
│   │   └── STORY-005 ({{TITLE}})
│   └── STORY-004 ({{TITLE}})
└── STORY-006 ({{TITLE}})
-->
</dependency_graph>

<!-- ============================================================ -->
<!-- BLOCKED STORIES                                               -->
<!-- ============================================================ -->

<blocked>
  <!-- TEMPLATE: List stories blocked on external dependencies -->
  <!-- TEMPLATE: Example: -->
  <!-- <item story="STORY-010" reason="Waiting for API v2 deployment" since="{{DATE}}" /> -->
  <!-- TEMPLATE: Remove this comment and leave empty when no stories are blocked -->
</blocked>

<!-- ============================================================ -->
<!-- PARKING LOT                                                   -->
<!-- ============================================================ -->

<parking_lot>
  <!-- TEMPLATE: Ideas for future consideration — not yet stories -->
  <idea>{{FUTURE_IDEA_1}}</idea>
  <idea>{{FUTURE_IDEA_2}}</idea>
  <idea>{{FUTURE_IDEA_3}}</idea>
</parking_lot>

<!-- ============================================================ -->
<!-- LABELS REFERENCE                                              -->
<!-- ============================================================ -->

<labels>
  <!-- TEMPLATE: Define labels used to categorize stories -->
  <label name="foundation">Core infrastructure and scaffolding</label>
  <label name="feature">New functionality</label>
  <label name="api">API integration</label>
  <label name="{{LABEL_NAME}}">{{LABEL_DESCRIPTION}}</label>
  <label name="mvp">Required for MVP</label>
  <label name="post-mvp">Post-MVP feature</label>
</labels>

</backlog>
