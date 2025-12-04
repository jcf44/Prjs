"""
Requirements Traceability Matrix Service

This service manages traceability matrices, including:
- Loading/importing from Excel/CSV files
- Storing in MongoDB
- Looking up documents for requirements
- Integration with RAG for enhanced context
"""

import os
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import structlog

from backend.domain.traceability import (
    TraceabilityMatrix, 
    Requirement, 
    TraceLink,
    TraceType, 
    RequirementStatus, 
    RequirementPriority
)
from backend.database import get_database

logger = structlog.get_logger()


class TraceabilityService:
    """
    Service for managing requirements traceability matrices.
    """
    
    def __init__(self):
        self.collection_name = "traceability_matrices"
        self.requirements_collection = "requirements"
    
    async def get_matrices_collection(self):
        db = await get_database()
        return db[self.collection_name]
    
    async def get_requirements_collection(self):
        db = await get_database()
        return db[self.requirements_collection]

    # =========================================================================
    # Excel/CSV Import
    # =========================================================================
    
    def load_matrix_from_excel(
        self, 
        file_path: str, 
        project_id: str,
        sheet_name: str = "Requirements"
    ) -> TraceabilityMatrix:
        """
        Load a traceability matrix from an Excel file.
        
        Expected Excel structure:
        - Sheet "Requirements": Main requirements data
        - Sheet "TraceLinks" (optional): Detailed trace links
        
        Requirements sheet columns:
        - requirement_id (required)
        - title (required)
        - description (required)
        - category
        - priority (must/should/could/wont)
        - status
        - source_reference
        - parent_requirement_id
        - tags (comma-separated)
        - source_docs (comma-separated paths)
        - design_docs (comma-separated paths)
        - implementation_docs (comma-separated paths)
        - verification_docs (comma-separated paths)
        """
        logger.info("Loading traceability matrix from Excel", file_path=file_path)
        
        # Read the main requirements sheet
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Clean column names (lowercase, strip whitespace)
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        
        requirements = []
        for _, row in df.iterrows():
            req = self._parse_requirement_row(row, project_id)
            if req:
                requirements.append(req)
        
        # Try to load detailed trace links if sheet exists
        try:
            links_df = pd.read_excel(file_path, sheet_name="TraceLinks")
            self._apply_trace_links(requirements, links_df)
        except Exception:
            logger.debug("No TraceLinks sheet found, using inline links only")
        
        matrix = TraceabilityMatrix(
            matrix_id=str(uuid.uuid4()),
            project_id=project_id,
            name=os.path.basename(file_path),
            description=f"Imported from {file_path}",
            requirements=requirements,
            source_file=file_path
        )
        
        logger.info(
            "Matrix loaded successfully", 
            requirement_count=len(requirements),
            file_path=file_path
        )
        return matrix

    def load_matrix_from_csv(
        self, 
        file_path: str, 
        project_id: str
    ) -> TraceabilityMatrix:
        """
        Load a traceability matrix from a CSV file.
        Same column structure as Excel Requirements sheet.
        """
        logger.info("Loading traceability matrix from CSV", file_path=file_path)
        
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        
        requirements = []
        for _, row in df.iterrows():
            req = self._parse_requirement_row(row, project_id)
            if req:
                requirements.append(req)
        
        matrix = TraceabilityMatrix(
            matrix_id=str(uuid.uuid4()),
            project_id=project_id,
            name=os.path.basename(file_path),
            description=f"Imported from {file_path}",
            requirements=requirements,
            source_file=file_path
        )
        
        logger.info(
            "Matrix loaded from CSV", 
            requirement_count=len(requirements)
        )
        return matrix

    def _parse_requirement_row(self, row: pd.Series, project_id: str) -> Optional[Requirement]:
        """Parse a single row into a Requirement object"""
        try:
            # Required fields
            req_id = str(row.get('requirement_id', row.get('req_id', ''))).strip()
            if not req_id or req_id == 'nan':
                return None
            
            title = str(row.get('title', '')).strip()
            description = str(row.get('description', '')).strip()
            
            # Optional fields with defaults
            category = self._safe_str(row.get('category'))
            priority_str = self._safe_str(row.get('priority'), 'should')
            status_str = self._safe_str(row.get('status'), 'draft')
            source_ref = self._safe_str(row.get('source_reference'))
            parent_id = self._safe_str(row.get('parent_requirement_id'))
            tags_str = self._safe_str(row.get('tags'), '')
            
            # Parse priority and status
            priority = self._parse_priority(priority_str)
            status = self._parse_status(status_str)
            
            # Parse tags
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            # Build trace links from inline columns
            trace_links = []
            
            # Source documents
            source_docs = self._parse_doc_list(row.get('source_docs'))
            for doc in source_docs:
                trace_links.append(TraceLink(
                    link_id=str(uuid.uuid4()),
                    trace_type=TraceType.SOURCE,
                    document_path=doc
                ))
            
            # Design documents
            design_docs = self._parse_doc_list(row.get('design_docs'))
            for doc in design_docs:
                trace_links.append(TraceLink(
                    link_id=str(uuid.uuid4()),
                    trace_type=TraceType.DESIGN,
                    document_path=doc
                ))
            
            # Implementation documents
            impl_docs = self._parse_doc_list(row.get('implementation_docs'))
            for doc in impl_docs:
                trace_links.append(TraceLink(
                    link_id=str(uuid.uuid4()),
                    trace_type=TraceType.IMPLEMENTATION,
                    document_path=doc
                ))
            
            # Verification documents
            verify_docs = self._parse_doc_list(row.get('verification_docs'))
            for doc in verify_docs:
                trace_links.append(TraceLink(
                    link_id=str(uuid.uuid4()),
                    trace_type=TraceType.VERIFICATION,
                    document_path=doc
                ))
            
            # Reference documents
            ref_docs = self._parse_doc_list(row.get('reference_docs'))
            for doc in ref_docs:
                trace_links.append(TraceLink(
                    link_id=str(uuid.uuid4()),
                    trace_type=TraceType.REFERENCE,
                    document_path=doc
                ))
            
            return Requirement(
                requirement_id=req_id,
                project_id=project_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                status=status,
                source_reference=source_ref,
                parent_requirement_id=parent_id,
                tags=tags,
                trace_links=trace_links
            )
            
        except Exception as e:
            logger.warning("Failed to parse requirement row", error=str(e), row=dict(row))
            return None

    def _apply_trace_links(self, requirements: List[Requirement], links_df: pd.DataFrame):
        """Apply detailed trace links from a separate sheet"""
        links_df.columns = links_df.columns.str.lower().str.strip().str.replace(' ', '_')
        
        # Build a lookup map
        req_map = {req.requirement_id: req for req in requirements}
        
        for _, row in links_df.iterrows():
            req_id = str(row.get('requirement_id', '')).strip()
            if req_id not in req_map:
                continue
            
            trace_type_str = self._safe_str(row.get('trace_type'), 'reference')
            document_path = self._safe_str(row.get('document_path'))
            
            if not document_path:
                continue
            
            link = TraceLink(
                link_id=str(uuid.uuid4()),
                trace_type=self._parse_trace_type(trace_type_str),
                document_path=document_path,
                section=self._safe_str(row.get('section')),
                description=self._safe_str(row.get('description')),
                verified=bool(row.get('verified', False))
            )
            
            req_map[req_id].trace_links.append(link)

    def _safe_str(self, value, default: str = None) -> Optional[str]:
        """Safely convert value to string, handling NaN"""
        if pd.isna(value):
            return default
        return str(value).strip() if value else default

    def _parse_doc_list(self, value) -> List[str]:
        """Parse a comma-separated list of document paths"""
        if pd.isna(value) or not value:
            return []
        return [doc.strip() for doc in str(value).split(',') if doc.strip()]

    def _parse_priority(self, value: str) -> RequirementPriority:
        """Parse priority string to enum"""
        mapping = {
            'must': RequirementPriority.MUST,
            'should': RequirementPriority.SHOULD,
            'could': RequirementPriority.COULD,
            'wont': RequirementPriority.WONT,
            "won't": RequirementPriority.WONT,
        }
        return mapping.get(value.lower(), RequirementPriority.SHOULD)

    def _parse_status(self, value: str) -> RequirementStatus:
        """Parse status string to enum"""
        mapping = {
            'draft': RequirementStatus.DRAFT,
            'approved': RequirementStatus.APPROVED,
            'in_progress': RequirementStatus.IN_PROGRESS,
            'in progress': RequirementStatus.IN_PROGRESS,
            'implemented': RequirementStatus.IMPLEMENTED,
            'verified': RequirementStatus.VERIFIED,
            'deferred': RequirementStatus.DEFERRED,
            'rejected': RequirementStatus.REJECTED,
        }
        return mapping.get(value.lower(), RequirementStatus.DRAFT)

    def _parse_trace_type(self, value: str) -> TraceType:
        """Parse trace type string to enum"""
        mapping = {
            'source': TraceType.SOURCE,
            'design': TraceType.DESIGN,
            'implementation': TraceType.IMPLEMENTATION,
            'impl': TraceType.IMPLEMENTATION,
            'verification': TraceType.VERIFICATION,
            'test': TraceType.VERIFICATION,
            'reference': TraceType.REFERENCE,
            'ref': TraceType.REFERENCE,
        }
        return mapping.get(value.lower(), TraceType.REFERENCE)

    # =========================================================================
    # Database Operations
    # =========================================================================

    async def save_matrix(self, matrix: TraceabilityMatrix) -> str:
        """Save a traceability matrix to MongoDB"""
        collection = await self.get_matrices_collection()
        
        # Check if matrix already exists
        existing = await collection.find_one({
            "matrix_id": matrix.matrix_id
        })
        
        matrix.updated_at = datetime.now()
        matrix_dict = matrix.model_dump(mode="json")
        
        if existing:
            await collection.replace_one(
                {"matrix_id": matrix.matrix_id},
                matrix_dict
            )
            logger.info("Updated traceability matrix", matrix_id=matrix.matrix_id)
        else:
            await collection.insert_one(matrix_dict)
            logger.info("Created traceability matrix", matrix_id=matrix.matrix_id)
        
        return matrix.matrix_id

    async def get_matrix(self, matrix_id: str) -> Optional[TraceabilityMatrix]:
        """Get a traceability matrix by ID"""
        collection = await self.get_matrices_collection()
        doc = await collection.find_one({"matrix_id": matrix_id})
        
        if doc:
            return TraceabilityMatrix(**doc)
        return None

    async def get_matrices_for_project(self, project_id: str) -> List[TraceabilityMatrix]:
        """Get all matrices for a project"""
        collection = await self.get_matrices_collection()
        cursor = collection.find({"project_id": project_id})
        
        matrices = []
        async for doc in cursor:
            matrices.append(TraceabilityMatrix(**doc))
        return matrices

    async def delete_matrix(self, matrix_id: str) -> bool:
        """Delete a traceability matrix"""
        collection = await self.get_matrices_collection()
        result = await collection.delete_one({"matrix_id": matrix_id})
        return result.deleted_count > 0

    # =========================================================================
    # Lookup Operations
    # =========================================================================

    async def find_requirement(
        self, 
        project_id: str, 
        requirement_id: str
    ) -> Optional[Requirement]:
        """Find a specific requirement by ID within a project"""
        matrices = await self.get_matrices_for_project(project_id)
        
        for matrix in matrices:
            req = matrix.get_requirement(requirement_id)
            if req:
                return req
        return None

    async def search_requirements(
        self,
        project_id: str,
        query: str,
        category: Optional[str] = None,
        status: Optional[RequirementStatus] = None
    ) -> List[Requirement]:
        """
        Search requirements by text in title/description.
        Optionally filter by category and status.
        """
        matrices = await self.get_matrices_for_project(project_id)
        results = []
        query_lower = query.lower()
        
        for matrix in matrices:
            for req in matrix.requirements:
                # Text match
                if query_lower not in req.title.lower() and \
                   query_lower not in req.description.lower() and \
                   query_lower not in req.requirement_id.lower():
                    continue
                
                # Filter by category
                if category and req.category != category:
                    continue
                
                # Filter by status
                if status and req.status != status:
                    continue
                
                results.append(req)
        
        return results

    async def get_documents_for_requirement(
        self,
        project_id: str,
        requirement_id: str,
        trace_types: Optional[List[TraceType]] = None
    ) -> List[TraceLink]:
        """
        Get all document links for a requirement.
        Optionally filter by trace type.
        """
        req = await self.find_requirement(project_id, requirement_id)
        if not req:
            return []
        
        if trace_types:
            return [link for link in req.trace_links if link.trace_type in trace_types]
        return req.trace_links

    async def find_requirements_for_document(
        self,
        project_id: str,
        document_path: str
    ) -> List[Requirement]:
        """
        Reverse lookup: find all requirements that trace to a specific document.
        Useful for impact analysis.
        """
        matrices = await self.get_matrices_for_project(project_id)
        results = []
        
        # Normalize path for comparison
        doc_path_normalized = document_path.replace('\\', '/').lower()
        
        for matrix in matrices:
            for req in matrix.requirements:
                for link in req.trace_links:
                    link_path_normalized = link.document_path.replace('\\', '/').lower()
                    if doc_path_normalized in link_path_normalized or \
                       link_path_normalized in doc_path_normalized:
                        results.append(req)
                        break  # Don't add same req twice
        
        return results

    async def get_coverage_report(self, project_id: str) -> Dict[str, Any]:
        """Generate a combined coverage report for all matrices in a project"""
        matrices = await self.get_matrices_for_project(project_id)
        
        combined = {
            "project_id": project_id,
            "matrices_count": len(matrices),
            "total_requirements": 0,
            "by_status": {},
            "by_trace_type": {t.value: 0 for t in TraceType},
            "fully_traced": 0,
            "untraced": 0,
            "matrices": []
        }
        
        for matrix in matrices:
            report = matrix.coverage_report()
            combined["total_requirements"] += report["total_requirements"]
            combined["fully_traced"] += report["fully_traced"]
            combined["untraced"] += report["untraced"]
            
            for status, count in report["by_status"].items():
                combined["by_status"][status] = combined["by_status"].get(status, 0) + count
            
            for trace_type, count in report["by_trace_type"].items():
                combined["by_trace_type"][trace_type] += count
            
            combined["matrices"].append({
                "matrix_id": matrix.matrix_id,
                "name": matrix.name,
                "report": report
            })
        
        # Calculate percentages
        total = combined["total_requirements"]
        if total > 0:
            combined["trace_coverage_pct"] = round(
                (total - combined["untraced"]) / total * 100, 1
            )
            combined["full_coverage_pct"] = round(
                combined["fully_traced"] / total * 100, 1
            )
        else:
            combined["trace_coverage_pct"] = 0
            combined["full_coverage_pct"] = 0
        
        return combined


# Singleton instance
_traceability_service: TraceabilityService | None = None

def get_traceability_service() -> TraceabilityService:
    global _traceability_service
    if _traceability_service is None:
        _traceability_service = TraceabilityService()
    return _traceability_service
