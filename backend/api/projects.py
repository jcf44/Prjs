from fastapi import APIRouter, Depends, HTTPException, Form
from typing import List
from backend.services.project import get_project_service, ProjectService
from backend.domain.project import Project
import structlog

router = APIRouter(prefix="/v1/projects", tags=["projects"])
logger = structlog.get_logger()

@router.get("/", response_model=List[Project])
async def list_projects(
    user_profile: str = "default",
    project_service: ProjectService = Depends(get_project_service)
):
    """List all projects for a user"""
    # Ensure default project exists
    await project_service.ensure_default_project(user_profile)
    return await project_service.list_projects(user_profile)

@router.post("/", response_model=Project)
async def create_project(
    name: str = Form(...),
    description: str = Form(None),
    user_profile: str = Form("default"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Create a new project"""
    return await project_service.create_project(name, user_profile, description)

@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a project by ID"""
    project = await project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete a project"""
    success = await project_service.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted", "project_id": project_id}
