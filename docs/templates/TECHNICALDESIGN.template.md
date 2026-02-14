# Technical Design - {{PROJECT_NAME}}

<!-- TEMPLATE: This document is OPTIONAL. Use it when your project needs detailed -->
<!-- schema/API specifications beyond what Architecture.md covers. -->
<!-- TEMPLATE: If Architecture.md is sufficient for your project, you do not need this file. -->
<!-- TEMPLATE: When used, it supplements (not replaces) Architecture.md. -->

**Last Updated**: {{DATE}}
**Version**: 1.0

---

## Overview

This document contains detailed technical specifications for {{PROJECT_NAME}}.
It supplements Architecture.md with implementation details such as data model schemas,
database table definitions, API endpoint specifications, and validation rules.

**When to use this document**: When a story requires detailed schema knowledge, specific
API contracts, or complex validation rules that would clutter Architecture.md.

---

## Data Models

<!-- TEMPLATE: Document your data structures in detail -->
<!-- TEMPLATE: Use {{LANGUAGE}}-appropriate type notation -->

### {{MODEL_NAME}}

**Purpose**: {{MODEL_PURPOSE}}

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | {{ID_TYPE}} | Yes | Primary identifier |
| `{{field_1}}` | {{TYPE}} | Yes | {{DESCRIPTION}} |
| `{{field_2}}` | {{TYPE}} | No | {{DESCRIPTION}} |
| `created_at` | DateTime | Yes | Creation timestamp |
| `updated_at` | DateTime | Yes | Last update timestamp |

**Validation Rules**:
- `{{field_1}}`: {{VALIDATION_RULE}}
- `{{field_2}}`: {{VALIDATION_RULE}}

**JSON Example**:
```json
{
  "id": "{{EXAMPLE_ID}}",
  "{{field_1}}": "{{EXAMPLE_VALUE}}",
  "{{field_2}}": "{{EXAMPLE_VALUE}}",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### {{ANOTHER_MODEL_NAME}}

<!-- Repeat model template above -->

---

## Database Schema

<!-- TEMPLATE: Document your database tables -->
<!-- TEMPLATE: Use standard SQL — adapt syntax for your specific database -->

### Tables

#### {{TABLE_NAME}}
```sql
CREATE TABLE {{table_name}} (
    id {{ID_TYPE}} PRIMARY KEY,
    {{column_1}} {{TYPE}} NOT NULL,
    {{column_2}} {{TYPE}},
    created_at {{TIMESTAMP_TYPE}} NOT NULL,
    updated_at {{TIMESTAMP_TYPE}} NOT NULL,
    FOREIGN KEY ({{fk_column}}) REFERENCES {{parent_table}}(id)
);

CREATE INDEX idx_{{table_name}}_{{column}} ON {{table_name}}({{column}});
```

**Purpose**: {{TABLE_PURPOSE}}

**Relationships**:
- One-to-Many with {{RELATED_TABLE}}
- Many-to-One with {{PARENT_TABLE}}

---

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│  {{TABLE_1}}    │       │  {{TABLE_2}}    │
├─────────────────┤       ├─────────────────┤
│ PK id           │───┐   │ PK id           │
│    name         │   │   │ FK {{fk}}       │◄──┐
│    created_at   │   │   │    field        │   │
└─────────────────┘   │   └─────────────────┘   │
                      │                          │
                      └──────────────────────────┘
```

---

### Views

#### {{VIEW_NAME}}
```sql
CREATE VIEW {{view_name}} AS
SELECT
    t1.id,
    t1.name,
    t2.field
FROM {{table_1}} t1
JOIN {{table_2}} t2 ON t1.id = t2.{{fk}};
```

**Purpose**: {{VIEW_PURPOSE}}

---

## API Specifications

<!-- TEMPLATE: Document your API endpoints in detail -->
<!-- TEMPLATE: This section is for APIs your project consumes or exposes -->

### {{ENDPOINT_GROUP}}

#### {{HTTP_METHOD}} {{ENDPOINT_PATH}}

**Description**: {{ENDPOINT_DESCRIPTION}}

**Request**:
```http
{{HTTP_METHOD}} {{ENDPOINT_PATH}}
Content-Type: application/json
{{AUTH_HEADER}}: {{AUTH_VALUE}}

{
  "{{field}}": "{{value}}"
}
```

**Request Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `{{param}}` | {{TYPE}} | Yes | {{DESCRIPTION}} |

**Response** (200 OK):
```json
{
  "data": {
    "id": "{{EXAMPLE_ID}}",
    "{{field}}": "{{value}}"
  }
}
```

**Error Responses**:
| Status | Code | Description |
|--------|------|-------------|
| 400 | `invalid_request` | {{DESCRIPTION}} |
| 404 | `not_found` | {{DESCRIPTION}} |
| 500 | `internal_error` | {{DESCRIPTION}} |

**Error Response Format** (RFC 7807):
```json
{
  "type": "https://{{domain}}/errors/{{error_type}}",
  "title": "{{Error Title}}",
  "status": {{STATUS_CODE}},
  "detail": "{{Detailed error message}}",
  "instance": "{{request_path}}"
}
```

---

## Processing Pipelines

<!-- TEMPLATE: Document data processing flows -->
<!-- TEMPLATE: Remove this section if not applicable -->

### {{PIPELINE_NAME}}

**Purpose**: {{PIPELINE_PURPOSE}}

**Steps**:
```
Step 1: {{STEP_NAME}}
├── Input: {{INPUT_DESCRIPTION}}
├── Process: {{PROCESS_DESCRIPTION}}
├── Output: {{OUTPUT_DESCRIPTION}}
└── Errors: {{ERROR_HANDLING}}
        ↓
Step 2: {{STEP_NAME}}
├── Input: {{INPUT_DESCRIPTION}}
├── Process: {{PROCESS_DESCRIPTION}}
└── Output: {{OUTPUT_DESCRIPTION}}
        ↓
Step 3: {{STEP_NAME}}
└── ...
```

**Idempotency**: {{IDEMPOTENCY_DESCRIPTION}}

**Error Handling**: {{ERROR_HANDLING_STRATEGY}}

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `{{VAR_NAME}}` | {{DESCRIPTION}} | {{DEFAULT}} | Yes/No |

### Configuration Pattern

<!-- TEMPLATE: Use a pattern appropriate for your language and framework -->

```{{LANGUAGE_ID}}
// {{SOURCE_DIR}}/config/{{CONFIG_FILE}}

// Example: Configuration class with defaults and environment overrides
// Adapt the syntax and pattern to your language (e.g., pydantic for Python,
// environment variables for Node, SharedPreferences for mobile)

{{CONFIG_EXAMPLE}}
```

---

## Validation Rules

<!-- TEMPLATE: Document business logic validation -->

### {{DOMAIN_ENTITY}}

| Field | Rule | Error Message |
|-------|------|---------------|
| `{{field}}` | {{RULE}} | {{ERROR_MESSAGE}} |

### Cross-Field Validation

| Validation | Fields | Rule |
|------------|--------|------|
| {{NAME}} | {{FIELDS}} | {{RULE}} |

---

## Security Specifications

### Authentication

**Method**: {{AUTH_METHOD}}

**Token/Key Format**:
```
{{AUTH_HEADER}}: {{AUTH_VALUE_FORMAT}}
```

**Lifecycle**: {{TOKEN_LIFECYCLE}}

### Authorization

| Role | Permissions |
|------|-------------|
| `{{role_1}}` | {{PERMISSIONS}} |
| `{{role_2}}` | {{PERMISSIONS}} |

### Rate Limiting

| Tier | Limit | Window |
|------|-------|--------|
| Default | {{LIMIT}} | {{WINDOW}} |

---

## Performance Requirements

<!-- TEMPLATE: Remove this section if not applicable -->

| Metric | Target | Measurement |
|--------|--------|-------------|
| Response time (p95) | < {{MS}}ms | {{MEASUREMENT}} |
| Throughput | {{RPS}} req/s | {{MEASUREMENT}} |
| Availability | {{PERCENT}}% | Monthly |

---

## Monitoring & Observability

<!-- TEMPLATE: Remove this section if not applicable -->

### Logging

**Format**: {{LOG_FORMAT}}

### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `{{metric_name}}` | Counter | {{DESCRIPTION}} |
| `{{metric_name}}` | Histogram | {{DESCRIPTION}} |

### Health Checks

| Endpoint | Checks | Healthy Response |
|----------|--------|------------------|
| `{{HEALTH_ENDPOINT}}` | {{CHECKS}} | `{{RESPONSE}}` |

---

## Migration Strategy

<!-- TEMPLATE: Document how database schema changes are managed -->
<!-- TEMPLATE: Remove this section if not applicable -->

### Database Migrations

**Location**: `{{MIGRATION_DIR}}/`

**Naming Convention**: `{{NAMING_PATTERN}}`

**Migration approach**: {{MIGRATION_TOOL_OR_PATTERN}}

---

## External Dependencies

| Dependency | Purpose | Version | Documentation |
|------------|---------|---------|---------------|
| {{PACKAGE}} | {{PURPOSE}} | {{VERSION}} | {{URL}} |

---

## Glossary

| Term | Definition |
|------|------------|
| {{TERM}} | {{DEFINITION}} |
