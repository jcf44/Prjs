"""
Traceability Matrix API Endpoints

Provides REST API for:
- Importing traceability matrices from Excel/CSV
- Managing requirements and trace links
- Querying with traceability-aware RAG
- Coverage reports
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import tempfile
import shutil

from backend.services.traceability import get_traceability_service
from backend.services.enhanced_rag import get_enhanced_rag_service
from backend.domain.traceability import (
    TraceabilityMatrix,
    Requirement,
    TraceType,
    RequirementStatus,
    RequirementPriority
)
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/traceability", tags=["traceability"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ImportMatrixResponse(BaseModel):
    matrix_id: str
    name: str
    requirement_count: int
    message: str


class RequirementSummary(BaseModel):
    requirement_id: str
    title: str
    status: str
    priority: str
    category: Optional[str]
    trace_count: int


class MatrixSummary(BaseModel):
    matrix_id: str
    name: str
    requirement_count: int
    created_at: str
    source_file: Optional[str]


class TraceLinkCreate(BaseModel):
    trace_type: str  # source, design, implementation, verification, reference
    document_path: str
    section: Optional[str] = None
    description: Optional[str] = None


class RequirementQuery(BaseModel):
    query: str
    use_traceability: bool = True
    use_semantic: bool = True
    trace_types: Optional[List[str]] = None  # Filter by trace type
    model: Optional[str] = None


class RequirementDirectQuery(BaseModel):
    requirement_id: str
    question: Optional[str] = None
    trace_types: Optional[List[str]] = None
    model: Optional[str] = None


# =============================================================================
# Matrix Management Endpoints
# =============================================================================

@router.post("/import", response_model=ImportMatrixResponse)
async def import_matrix(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    sheet_name: str = Form("Requirements")
):
    """
    Import a traceability matrix from Excel (.xlsx) or CSV file.
    
    Expected columns:
    - requirement_id (required)
    - title (required)
    - description (required)
    - category, priority, status, source_reference, parent_requirement_id, tags
    - source_docs, design_docs, implementation_docs, verification_docs (comma-separated paths)
    """
    service = get_traceability_service()
    
    # Validate file type
    filename = file.filename.lower()
    if not filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(
            status_code=400,
            detail="File must be .xlsx or .csv"
        )
    
    # Save uploaded file temporarily
    suffix = '.xlsx' if filename.endswith('.xlsx') else '.csv'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    try:
        # Load matrix from file
        if filename.endswith('.xlsx'):
            matrix = service.load_matrix_from_excel(tmp_path, project_id, sheet_name)
        else:
            matrix = service.load_matrix_from_csv(tmp_path, project_id)
        
        # Save to database
        await service.save_matrix(matrix)
        
        return ImportMatrixResponse(
            matrix_id=matrix.matrix_id,
            name=matrix.name,
            requirement_count=len(matrix.requirements),
            message=f"Successfully imported {len(matrix.requirements)} requirements"
        )
    
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@router.get("/matrices/{project_id}", response_model=List[MatrixSummary])
async def list_matrices(project_id: str):
    """List all traceability matrices for a project."""
    service = get_traceability_service()
    matrices = await service.get_matrices_for_project(project_id)
    
    return [
        MatrixSummary(
            matrix_id=m.matrix_id,
            name=m.name,
            requirement_count=len(m.requirements),
            created_at=m.created_at.isoformat(),
            source_file=m.source_file
        )
        for m in matrices
    ]


@router.get("/matrix/{matrix_id}")
async def get_matrix(matrix_id: str):
    """Get full details of a traceability matrix."""
    service = get_traceability_service()
    matrix = await service.get_matrix(matrix_id)
    
    if not matrix:
        raise HTTPException(status_code=404, detail="Matrix not found")
    
    return matrix.model_dump(mode="json")


@router.delete("/matrix/{matrix_id}")
async def delete_matrix(matrix_id: str):
    """Delete a traceability matrix."""
    service = get_traceability_service()
    success = await service.delete_matrix(matrix_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Matrix not found")
    
    return {"message": "Matrix deleted successfully"}


# =============================================================================
# Requirements Endpoints
# =============================================================================

@router.get("/requirements/{project_id}", response_model=List[RequirementSummary])
async def list_requirements(
    project_id: str,
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """List requirements in a project with optional filtering."""
    service = get_traceability_service()
    matrices = await service.get_matrices_for_project(project_id)
    
    results = []
    for matrix in matrices:
        for req in matrix.requirements:
            # Apply filters
            if category and req.category != category:
                continue
            if status and req.status.value != status:
                continue
            if search:
                search_lower = search.lower()
                if search_lower not in req.title.lower() and \
                   search_lower not in req.description.lower() and \
                   search_lower not in req.requirement_id.lower():
                    continue
            
            results.append(RequirementSummary(
                requirement_id=req.requirement_id,
                title=req.title,
                status=req.status.value,
                priority=req.priority.value,
                category=req.category,
                trace_count=len(req.trace_links)
            ))
    
    return results


@router.get("/requirement/{project_id}/{requirement_id}")
async def get_requirement(project_id: str, requirement_id: str):
    """Get full details of a specific requirement."""
    service = get_traceability_service()
    req = await service.find_requirement(project_id, requirement_id)
    
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    return req.model_dump(mode="json")


@router.get("/requirement/{project_id}/{requirement_id}/documents")
async def get_requirement_documents(
    project_id: str,
    requirement_id: str,
    trace_type: Optional[str] = Query(None)
):
    """Get all traced documents for a requirement."""
    service = get_traceability_service()
    
    trace_types = None
    if trace_type:
        try:
            trace_types = [TraceType(trace_type)]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid trace type: {trace_type}")
    
    links = await service.get_documents_for_requirement(
        project_id, requirement_id, trace_types
    )
    
    return [link.model_dump(mode="json") for link in links]


@router.get("/document/{project_id}/requirements")
async def get_document_requirements(
    project_id: str,
    document_path: str = Query(...)
):
    """
    Reverse lookup: find all requirements that trace to a document.
    Useful for impact analysis when a document changes.
    """
    service = get_traceability_service()
    requirements = await service.find_requirements_for_document(project_id, document_path)
    
    return [
        RequirementSummary(
            requirement_id=req.requirement_id,
            title=req.title,
            status=req.status.value,
            priority=req.priority.value,
            category=req.category,
            trace_count=len(req.trace_links)
        )
        for req in requirements
    ]


# =============================================================================
# Coverage & Reporting
# =============================================================================

@router.get("/coverage/{project_id}")
async def get_coverage_report(project_id: str):
    """
    Get a traceability coverage report for a project.
    
    Shows:
    - Total requirements
    - Requirements by status
    - Trace link counts by type
    - Coverage percentages
    """
    service = get_traceability_service()
    report = await service.get_coverage_report(project_id)
    return report


# =============================================================================
# Enhanced RAG Queries
# =============================================================================

@router.post("/query/{project_id}")
async def query_with_traceability(project_id: str, request: RequirementQuery):
    """
    Query using enhanced RAG with traceability matrix integration.
    
    If the query mentions requirement IDs (e.g., REQ-001), the system
    will retrieve traced documents directly before falling back to
    semantic search.
    """
    service = get_enhanced_rag_service()
    
    # Parse trace types if provided
    trace_types = None
    if request.trace_types:
        trace_types = [TraceType(t) for t in request.trace_types]
    
    result = await service.query(
        query=request.query,
        project_id=project_id,
        model=request.model,
        use_traceability=request.use_traceability,
        use_semantic=request.use_semantic,
        trace_types=trace_types
    )
    
    return result


@router.post("/query-requirement/{project_id}")
async def query_specific_requirement(project_id: str, request: RequirementDirectQuery):
    """
    Query about a specific requirement.
    
    If no question is provided, returns a summary of the requirement
    and its traced documents.
    
    If a question is provided, answers using only the traced documents.
    """
    service = get_enhanced_rag_service()
    
    trace_types = None
    if request.trace_types:
        trace_types = [TraceType(t) for t in request.trace_types]
    
    result = await service.query_requirement(
        requirement_id=request.requirement_id,
        project_id=project_id,
        question=request.question,
        trace_types=trace_types,
        model=request.model
    )
    
    return result
