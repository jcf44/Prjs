"""
Requirements Traceability Matrix Domain Models

This module defines the data structures for managing requirements
and their traceability to documentation artifacts.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TraceType(str, Enum):
    """Type of traceability link"""
    SOURCE = "source"           # Where the requirement comes from (RFP, spec)
    DESIGN = "design"           # Design documents addressing the requirement
    IMPLEMENTATION = "implementation"  # Code, scripts, configurations
    VERIFICATION = "verification"      # Test cases, validation docs
    REFERENCE = "reference"     # Related reference material


class RequirementStatus(str, Enum):
    """Status of a requirement"""
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class RequirementPriority(str, Enum):
    """Priority levels for requirements"""
    MUST = "must"       # Must have (MoSCoW)
    SHOULD = "should"   # Should have
    COULD = "could"     # Could have
    WONT = "wont"       # Won't have (this iteration)


class TraceLink(BaseModel):
    """
    A link between a requirement and a document/artifact.
    
    This represents the actual traceability relationship.
    """
    link_id: str
    trace_type: TraceType
    document_path: str              # Path to the document (can be in corpus or external)
    document_source_id: Optional[str] = None  # Links to indexed document in vector DB
    section: Optional[str] = None   # Specific section/page reference
    description: Optional[str] = None
    verified: bool = False          # Has this trace been verified?
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class Requirement(BaseModel):
    """
    A requirement that needs to be traced to documentation.
    
    This is the central entity in the traceability matrix.
    """
    requirement_id: str             # Unique ID (e.g., "REQ-001", "FR-3.1.2")
    project_id: str                 # Links to Wendy project
    title: str                      # Short title
    description: str                # Full requirement text
    category: Optional[str] = None  # Category/grouping (e.g., "Functional", "Security")
    priority: RequirementPriority = RequirementPriority.SHOULD
    status: RequirementStatus = RequirementStatus.DRAFT
    source_reference: Optional[str] = None  # Original source (e.g., "RFP Section 3.1")
    parent_requirement_id: Optional[str] = None  # For hierarchical requirements
    tags: List[str] = Field(default_factory=list)
    trace_links: List[TraceLink] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    def get_links_by_type(self, trace_type: TraceType) -> List[TraceLink]:
        """Get all trace links of a specific type"""
        return [link for link in self.trace_links if link.trace_type == trace_type]
    
    def get_all_document_paths(self) -> List[str]:
        """Get all document paths from all trace links"""
        return [link.document_path for link in self.trace_links]
    
    def coverage_summary(self) -> Dict[str, int]:
        """Get count of links by type for coverage analysis"""
        summary = {t.value: 0 for t in TraceType}
        for link in self.trace_links:
            summary[link.trace_type.value] += 1
        return summary


class TraceabilityMatrix(BaseModel):
    """
    A complete traceability matrix for a project.
    
    This is the container that holds all requirements and their traces.
    Can be imported/exported from Excel/CSV.
    """
    matrix_id: str
    project_id: str
    name: str
    description: Optional[str] = None
    version: str = "1.0"
    requirements: List[Requirement] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    source_file: Optional[str] = None  # Path to source Excel/CSV if imported
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    def get_requirement(self, requirement_id: str) -> Optional[Requirement]:
        """Get a requirement by ID"""
        for req in self.requirements:
            if req.requirement_id == requirement_id:
                return req
        return None
    
    def get_requirements_by_status(self, status: RequirementStatus) -> List[Requirement]:
        """Filter requirements by status"""
        return [req for req in self.requirements if req.status == status]
    
    def get_requirements_by_category(self, category: str) -> List[Requirement]:
        """Filter requirements by category"""
        return [req for req in self.requirements if req.category == category]
    
    def coverage_report(self) -> Dict[str, Any]:
        """Generate a coverage report for the matrix"""
        total = len(self.requirements)
        if total == 0:
            return {"total": 0, "coverage": {}}
        
        coverage = {
            "total_requirements": total,
            "by_status": {},
            "by_trace_type": {t.value: 0 for t in TraceType},
            "fully_traced": 0,  # Has at least source + verification
            "untraced": 0,
        }
        
        for req in self.requirements:
            # Count by status
            status = req.status.value
            coverage["by_status"][status] = coverage["by_status"].get(status, 0) + 1
            
            # Count by trace type
            for link in req.trace_links:
                coverage["by_trace_type"][link.trace_type.value] += 1
            
            # Check if fully traced
            has_source = any(l.trace_type == TraceType.SOURCE for l in req.trace_links)
            has_verification = any(l.trace_type == TraceType.VERIFICATION for l in req.trace_links)
            
            if has_source and has_verification:
                coverage["fully_traced"] += 1
            elif len(req.trace_links) == 0:
                coverage["untraced"] += 1
        
        coverage["trace_coverage_pct"] = round(
            (total - coverage["untraced"]) / total * 100, 1
        )
        coverage["full_coverage_pct"] = round(
            coverage["fully_traced"] / total * 100, 1
        )
        
        return coverage
