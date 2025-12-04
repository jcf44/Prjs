# Requirements Traceability Matrix Module

## Overview

The Traceability Matrix module allows you to map **requirements** to their supporting **documentation artifacts**. This enables:

1. **Deterministic document retrieval**: When you ask about a specific requirement, Wendy fetches the exact documents that address it
2. **Coverage analysis**: See which requirements have proper documentation
3. **Impact analysis**: Find all requirements affected when a document changes
4. **Hybrid RAG**: Combine deterministic trace lookup with semantic search

## Concepts

### Trace Types

Each link between a requirement and a document has a type:

| Type | Description | Example |
|------|-------------|---------|
| `source` | Where the requirement comes from | RFP, Customer Spec, Regulatory Doc |
| `design` | Documents that design/architect the solution | Architecture.md, Design Spec |
| `implementation` | Code, scripts, configurations | /src/module.py, config.yaml |
| `verification` | Test cases, validation documents | TestCase_001.md, UAT Results |
| `reference` | Related reference material | API Docs, Standards |

### Requirement Status

| Status | Meaning |
|--------|---------|
| `draft` | Initial capture, not yet approved |
| `approved` | Approved for implementation |
| `in_progress` | Currently being implemented |
| `implemented` | Implementation complete |
| `verified` | Tested and verified |
| `deferred` | Postponed to future iteration |
| `rejected` | Not going to be implemented |

### Requirement Priority (MoSCoW)

| Priority | Meaning |
|----------|---------|
| `must` | Must have - critical |
| `should` | Should have - important |
| `could` | Could have - nice to have |
| `wont` | Won't have this iteration |

## Excel/CSV Format

### Simple Format (Single Sheet)

Create a CSV or Excel file with these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `requirement_id` | ✅ | Unique ID (e.g., REQ-001, FR-3.1) |
| `title` | ✅ | Short title |
| `description` | ✅ | Full requirement text |
| `category` | | Grouping (Functional, Security, etc.) |
| `priority` | | must/should/could/wont |
| `status` | | draft/approved/in_progress/etc. |
| `source_reference` | | Original source (e.g., "RFP Section 3.1") |
| `parent_requirement_id` | | For hierarchical requirements |
| `tags` | | Comma-separated tags |
| `source_docs` | | Comma-separated source document paths |
| `design_docs` | | Comma-separated design document paths |
| `implementation_docs` | | Comma-separated implementation paths |
| `verification_docs` | | Comma-separated test case paths |
| `reference_docs` | | Comma-separated reference paths |

### Example CSV

```csv
requirement_id,title,description,category,priority,status,source_docs,design_docs,verification_docs
REQ-001,User Login,Users shall authenticate via username/password,Security,must,approved,RFP.pdf,Auth_Design.md,TC_Login_001.md
REQ-002,Session Timeout,Sessions expire after 30 minutes of inactivity,Security,should,draft,RFP.pdf,Auth_Design.md,
```

### Advanced Format (Multiple Sheets in Excel)

For more detailed traceability, use an Excel file with two sheets:

**Sheet: Requirements**
- Same columns as above, but without the `*_docs` columns

**Sheet: TraceLinks**
| Column | Description |
|--------|-------------|
| `requirement_id` | Links to requirement |
| `trace_type` | source/design/implementation/verification/reference |
| `document_path` | Path to document |
| `section` | Specific section/page reference |
| `description` | Notes about this trace |
| `verified` | TRUE/FALSE - has trace been verified? |

## API Usage

### Import a Matrix

```bash
curl -X POST "http://localhost:8181/traceability/import" \
  -F "file=@matrix.xlsx" \
  -F "project_id=my-project" \
  -F "sheet_name=Requirements"
```

### List Requirements

```bash
# All requirements in a project
curl "http://localhost:8181/traceability/requirements/my-project"

# Filter by status
curl "http://localhost:8181/traceability/requirements/my-project?status=approved"

# Search by text
curl "http://localhost:8181/traceability/requirements/my-project?search=authentication"
```

### Get Requirement Details

```bash
curl "http://localhost:8181/traceability/requirement/my-project/REQ-001"
```

### Get Documents for a Requirement

```bash
# All traced documents
curl "http://localhost:8181/traceability/requirement/my-project/REQ-001/documents"

# Only design documents
curl "http://localhost:8181/traceability/requirement/my-project/REQ-001/documents?trace_type=design"
```

### Impact Analysis (Reverse Lookup)

Find all requirements that reference a document:

```bash
curl "http://localhost:8181/traceability/document/my-project/requirements?document_path=Architecture.md"
```

### Coverage Report

```bash
curl "http://localhost:8181/traceability/coverage/my-project"
```

Response:
```json
{
  "project_id": "my-project",
  "total_requirements": 25,
  "by_status": {
    "approved": 15,
    "in_progress": 7,
    "draft": 3
  },
  "by_trace_type": {
    "source": 25,
    "design": 20,
    "implementation": 12,
    "verification": 8,
    "reference": 5
  },
  "fully_traced": 8,
  "untraced": 2,
  "trace_coverage_pct": 92.0,
  "full_coverage_pct": 32.0
}
```

### Query with Traceability

Enhanced RAG that uses both traceability lookup and semantic search:

```bash
curl -X POST "http://localhost:8181/traceability/query/my-project" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How is REQ-001 implemented?",
    "use_traceability": true,
    "use_semantic": true
  }'
```

### Query Specific Requirement

```bash
# Get requirement summary
curl -X POST "http://localhost:8181/traceability/query-requirement/my-project" \
  -H "Content-Type: application/json" \
  -d '{"requirement_id": "REQ-001"}'

# Ask a question about it
curl -X POST "http://localhost:8181/traceability/query-requirement/my-project" \
  -H "Content-Type: application/json" \
  -d '{
    "requirement_id": "REQ-001",
    "question": "What are the security considerations?"
  }'
```

## How It Works

### Query Flow

```
User Query: "What are the design decisions for REQ-001?"
                    │
                    ▼
        ┌───────────────────────┐
        │ Detect Requirement ID │  ← Regex: REQ-001
        │   in query            │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Traceability Lookup   │  ← Get trace links from DB
        │ for REQ-001           │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Load traced documents │  ← Architecture.md, Design.docx
        │ (design type)         │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Semantic Search       │  ← Fill gaps with vector search
        │ (if enabled)          │     (excludes already-loaded docs)
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Build Context +       │  ← Combine all sources
        │ Call LLM              │
        └───────────┬───────────┘
                    │
                    ▼
              Response with
              source citations
```

## Best Practices

1. **Use consistent requirement IDs**: The system detects patterns like `REQ-001`, `FR-3.1`, `NFR-2`, etc.

2. **Keep documents indexed**: For best results, ensure traced documents are also indexed in the vector DB

3. **Use relative paths**: Store document paths relative to your corpus directory

4. **Regular coverage reviews**: Use the coverage report to identify gaps in documentation

5. **Version your matrix**: Keep your Excel/CSV in version control alongside your docs

## Integration with Existing RAG

The traceability module integrates seamlessly with Wendy's existing RAG:

- **Traceability first**: When a requirement is mentioned, traced documents are retrieved first
- **Semantic fills gaps**: Vector search supplements with additional relevant content
- **No duplicates**: Documents found via traceability are excluded from semantic results
- **Source attribution**: Responses indicate which retrieval method found each source
