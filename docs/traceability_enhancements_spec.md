# Traceability Matrix Module - Enhancement Specification

**Version:** 1.0  
**Date:** December 2025  
**Status:** Draft  

---

## Executive Summary

This document outlines enhancements to the existing Traceability Matrix module. The current implementation provides solid foundations (import, storage, lookup, RAG integration). These enhancements focus on: **intelligent auto-linking**, **UI/UX**, **verification workflows**, and **document change awareness**.

---

## Current State

### What Exists
- ✅ Domain models: `TraceabilityMatrix`, `Requirement`, `TraceLink`
- ✅ Excel/CSV import with flexible column mapping
- ✅ MongoDB storage for matrices and requirements
- ✅ REST API for CRUD operations
- ✅ Enhanced RAG combining traceability + semantic search
- ✅ Coverage reporting
- ✅ Impact analysis (reverse lookup)

### What's Missing
- ❌ Web UI for viewing/editing matrices
- ❌ Intelligent auto-linking suggestions
- ❌ Export back to Excel
- ❌ Document change detection
- ❌ Verification workflow with audit trail
- ❌ Section/chunk-level tracing
- ❌ Batch operations

---

## Enhancement 1: LLM-Assisted Auto-Linking

### Concept
Use the LLM to analyze requirements and suggest relevant documents from the corpus automatically.

### How It Works
```
1. User imports requirements (no trace links yet)
2. For each requirement, system:
   a. Searches vector DB using requirement description
   b. Sends top candidates to LLM with prompt:
      "Does this document address requirement X? Rate 1-5."
   c. Suggests high-confidence matches for user confirmation
3. User reviews/approves suggestions → becomes trace links
```

### API Additions
```
POST /traceability/suggest-links/{project_id}/{requirement_id}
  → Returns: List of {document_path, confidence, trace_type_suggestion, reasoning}

POST /traceability/approve-suggestion
  Body: {requirement_id, document_path, trace_type, approved: bool}
```

### Data Model Addition
```python
class TraceSuggestion(BaseModel):
    suggestion_id: str
    requirement_id: str
    document_path: str
    suggested_trace_type: TraceType
    confidence: float  # 0.0 - 1.0
    reasoning: str     # LLM explanation
    status: str        # pending, approved, rejected
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
```

### Developer Notes
- Use `VectorDBService.search()` to find candidate documents
- Prompt template should include requirement context + document excerpt
- Consider batching for efficiency (process 5-10 requirements at once)
- Store suggestions in MongoDB for user review
- Rate limit LLM calls (expensive)

---

## Enhancement 2: Section-Level Tracing

### Concept
Currently links to whole documents. Enhancement allows linking to specific sections/chunks already indexed in ChromaDB.

### How It Works
```
Requirement REQ-001 → Architecture.md, Section "Authentication Flow"
                    → Architecture.md, Section "Security Model"
```

### Data Model Changes
```python
class TraceLink(BaseModel):
    # ... existing fields ...
    chunk_ids: List[str] = []        # ChromaDB chunk IDs
    section_titles: List[str] = []   # Human-readable sections
    page_numbers: List[int] = []     # For PDFs
```

### Implementation Approach
1. When adding a trace link, optionally specify chunk IDs
2. Query flow:
   - If chunk_ids present → retrieve those specific chunks
   - If only document_path → load full document (current behavior)
3. UI shows section titles for user selection

### API Changes
```
GET /documents/{project_id}/{document_id}/chunks
  → Returns list of chunks with section titles, page numbers

POST /traceability/link
  Body: {requirement_id, document_path, chunk_ids?: [], trace_type}
```

---

## Enhancement 3: Web UI Components

### Required Views

#### 3.1 Matrix Overview Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ Project: SmartSpace Integration                    [Import] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Coverage: ████████████░░░░  78%     Fully Traced: 45%     │
│                                                             │
│  Requirements: 32    │  By Status         │  By Priority    │
│  Traced: 25          │  ● Approved: 18    │  ● Must: 12     │
│  Untraced: 7         │  ● Draft: 8        │  ● Should: 15   │
│                      │  ● Verified: 6     │  ● Could: 5     │
│                                                             │
│  [View Requirements]  [Gap Analysis]  [Export Matrix]       │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2 Requirements List View
```
┌─────────────────────────────────────────────────────────────┐
│ Requirements                           [+ Add] [Import CSV] │
├─────────────────────────────────────────────────────────────┤
│ Filter: [All Status ▼] [All Category ▼]  Search: [_______] │
├─────────────────────────────────────────────────────────────┤
│ ID       │ Title              │ Status   │ Traces │ Actions │
│──────────┼────────────────────┼──────────┼────────┼─────────│
│ REQ-001  │ User Auth          │ ✓ Verified│ 5/5   │ [Edit]  │
│ REQ-002  │ Session Timeout    │ ◐ Progress│ 3/5   │ [Edit]  │
│ REQ-003  │ Data Encryption    │ ○ Draft   │ 0/5   │ [Edit]  │
└─────────────────────────────────────────────────────────────┘
```

#### 3.3 Requirement Detail View
```
┌─────────────────────────────────────────────────────────────┐
│ REQ-001: User Authentication                                │
├─────────────────────────────────────────────────────────────┤
│ Status: [Approved ▼]    Priority: [Must ▼]                  │
│ Category: Security      Source: RFP Section 3.1             │
├─────────────────────────────────────────────────────────────┤
│ Description:                                                │
│ Users shall authenticate using username and password.       │
│ Passwords must meet complexity requirements defined in...   │
├─────────────────────────────────────────────────────────────┤
│ TRACE LINKS                                                 │
│                                                             │
│ Source Documents:                                           │
│   ✓ RFP_SmartSpace.pdf (Section 3.1)          [Remove]     │
│   + [Add Source Document]                                   │
│                                                             │
│ Design Documents:                                           │
│   ✓ Authentication_Design.md                  [Remove]     │
│   + [Add Design Document]                                   │
│                                                             │
│ Implementation:                                             │
│   ✓ /src/auth/login.py                        [Remove]     │
│   + [Add Implementation]                                    │
│                                                             │
│ Verification:                                               │
│   ○ (none - needs attention)                                │
│   + [Add Test Case]                                         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ SUGGESTIONS (AI-Generated)                     [Refresh]    │
│   ? TC_Auth_001.md (93% confidence)      [Accept] [Reject] │
│   ? Security_Standards.pdf (78%)          [Accept] [Reject] │
├─────────────────────────────────────────────────────────────┤
│ [Ask About This Requirement]   [View Impact]   [Save]       │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Components Needed
```
/frontend/src/components/traceability/
├── MatrixDashboard.tsx       # Overview with metrics
├── RequirementsList.tsx      # Filterable table
├── RequirementDetail.tsx     # Single requirement view
├── TraceLinkEditor.tsx       # Add/edit trace links
├── DocumentPicker.tsx        # Select documents from corpus
├── SuggestionsPanel.tsx      # AI suggestions review
├── CoverageChart.tsx         # Visual coverage metrics
├── GapAnalysis.tsx           # Missing traces report
└── ImportWizard.tsx          # Excel/CSV import UI
```

---

## Enhancement 4: Export Functionality

### Concept
Export the matrix back to Excel with all updates, coverage status, and change tracking.

### Export Formats
1. **Simple Export**: Same format as import (round-trip)
2. **Detailed Export**: Multi-sheet with full trace details
3. **Coverage Report**: Executive summary with charts

### API Addition
```
GET /traceability/export/{project_id}?format=xlsx|csv&include_coverage=true
  → Returns: File download
```

### Implementation Notes
- Use `openpyxl` for Excel generation
- Include timestamp and version in filename
- Option to include coverage statistics as separate sheet
- Support exporting subset (by status, category filter)

---

## Enhancement 5: Document Change Detection

### Concept
When a traced document is modified, alert users that trace verification may be needed.

### How It Works
```
1. Store file hash (SHA256) when trace link created
2. Background job periodically checks traced documents
3. If hash changes → mark trace as "needs_review"
4. Show in UI: "3 trace links may be outdated"
```

### Data Model Changes
```python
class TraceLink(BaseModel):
    # ... existing fields ...
    document_hash: Optional[str] = None
    last_verified_hash: Optional[str] = None
    needs_review: bool = False
    hash_changed_at: Optional[datetime] = None
```

### Background Service
```python
class TraceVerificationService:
    async def check_document_changes(self, project_id: str):
        """Run periodically (e.g., daily) to detect changes"""
        # For each trace link:
        #   1. Compute current file hash
        #   2. Compare with stored hash
        #   3. If different, set needs_review=True
```

### API Additions
```
POST /traceability/verify-link/{link_id}
  → Marks trace as verified, updates hash

GET /traceability/outdated-links/{project_id}
  → Returns links where needs_review=True
```

---

## Enhancement 6: Verification Workflow

### Concept
Formal workflow for verifying trace links with audit trail.

### States
```
UNVERIFIED → VERIFIED → (document changes) → NEEDS_REVIEW → VERIFIED
```

### Data Model Changes
```python
class VerificationRecord(BaseModel):
    verified_by: str
    verified_at: datetime
    verification_method: str  # "manual", "automated", "llm_assisted"
    notes: Optional[str]
    document_hash_at_verification: str

class TraceLink(BaseModel):
    # ... existing fields ...
    verification_history: List[VerificationRecord] = []
    current_verification_status: str  # "unverified", "verified", "needs_review"
```

### API Additions
```
POST /traceability/verify-link/{link_id}
  Body: {verified_by, notes, method}

GET /traceability/verification-history/{link_id}
  → Returns audit trail
```

---

## Enhancement 7: Integration with Document Ingestion

### Concept
When new documents are indexed, automatically suggest potential trace links.

### How It Works
```
1. Document ingested into ChromaDB
2. System queries all requirements for that project
3. For each requirement, check if new document is relevant
4. Create suggestions for user review
```

### Implementation Point
Add hook in `IngestionService.ingest_document()`:
```python
async def ingest_document(self, ...):
    # ... existing ingestion logic ...
    
    # After successful ingestion:
    if self.settings.AUTO_SUGGEST_TRACES:
        await self._suggest_traces_for_new_document(
            project_id, document_path, document_content
        )
```

---

## Priority Recommendation

| Enhancement | Priority | Effort | Value |
|-------------|----------|--------|-------|
| Web UI Components | High | 2-3 weeks | Essential for usability |
| Export Functionality | High | 2-3 days | Completes round-trip |
| LLM Auto-Linking | Medium | 1 week | Reduces manual work |
| Document Change Detection | Medium | 3-4 days | Ensures accuracy |
| Verification Workflow | Medium | 3-4 days | Audit/compliance |
| Section-Level Tracing | Low | 1 week | Precision improvement |
| Ingestion Integration | Low | 2-3 days | Nice-to-have |

### Suggested Implementation Order
1. **Export** - Quick win, enables full workflow
2. **Web UI** - Makes system usable for non-technical users
3. **Document Change Detection** - Ensures data integrity
4. **LLM Auto-Linking** - Reduces manual effort
5. **Verification Workflow** - Adds rigor
6. **Section-Level Tracing** - Refinement

---

## Technical Considerations

### Database Indexes (MongoDB)
```javascript
// Recommended indexes for performance
db.traceability_matrices.createIndex({project_id: 1})
db.traceability_matrices.createIndex({"requirements.requirement_id": 1})
db.traceability_matrices.createIndex({"requirements.trace_links.document_path": 1})
```

### File Hashing
```python
import hashlib

def compute_file_hash(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
```

### LLM Prompt Template (Auto-Linking)
```
You are analyzing whether a document addresses a requirement.

REQUIREMENT:
ID: {requirement_id}
Title: {title}
Description: {description}

DOCUMENT EXCERPT:
Source: {document_path}
Content: {excerpt}

TASK:
1. Does this document address the requirement? (yes/no/partially)
2. If yes, what trace type? (source/design/implementation/verification/reference)
3. Confidence score (1-5)
4. Brief reasoning (1-2 sentences)

Respond in JSON format.
```

---

## Open Questions for Product Decision

1. **Auto-linking approval**: Should suggestions require explicit approval, or auto-approve high-confidence matches?
2. **Change detection frequency**: Real-time (file watcher) vs. scheduled (daily)?
3. **Multi-user**: Do we need per-user verification tracking?
4. **Versioning**: Should we track matrix versions over time?
5. **Notifications**: Alert users when traces need review?

---

## Appendix: Sample Enhanced Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Import Matrix   │────▶│ Suggest Links   │────▶│ User Reviews    │
│ (Excel/CSV)     │     │ (LLM Analysis)  │     │ (Web UI)        │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Export Updated  │◀────│ Change Detection│◀────│ Verified Links  │
│ Matrix          │     │ (Background)    │     │ (MongoDB)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │ Alerts: "3 docs │
                        │ changed, review │
                        │ needed"         │
                        └─────────────────┘
```

---

*End of Specification*
