from typing import List, Optional
import uuid
from datetime import datetime
from backend.database import get_database
from backend.domain.project import Project
import structlog

logger = structlog.get_logger()

class ProjectService:
    def __init__(self):
        self.collection_name = "projects"

    async def get_collection(self):
        db = await get_database()
        return db[self.collection_name]

    async def create_project(self, name: str, user_profile: str, description: Optional[str] = None) -> Project:
        collection = await self.get_collection()
        project_id = str(uuid.uuid4())
        
        project = Project(
            project_id=project_id,
            name=name,
            description=description,
            user_profile=user_profile,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        await collection.insert_one(project.model_dump(mode="json"))
        logger.info("Created new project", project_id=project_id, name=name, user_profile=user_profile)
        return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        collection = await self.get_collection()
        doc = await collection.find_one({"project_id": project_id})
        
        if doc:
            return Project(**doc)
        return None

    async def list_projects(self, user_profile: str) -> List[Project]:
        collection = await self.get_collection()
        cursor = collection.find({"user_profile": user_profile}).sort("updated_at", -1)
        
        projects = []
        async for doc in cursor:
            projects.append(Project(**doc))
            
        return projects

    async def delete_project(self, project_id: str):
        collection = await self.get_collection()
        result = await collection.delete_one({"project_id": project_id})
        
        if result.deleted_count > 0:
            logger.info("Deleted project", project_id=project_id)
            return True
        return False
        
    async def ensure_default_project(self, user_profile: str) -> Project:
        """Ensures a default project exists for the user"""
        projects = await self.list_projects(user_profile)
        if not projects:
            logger.info("No projects found, creating default project", user_profile=user_profile)
            return await self.create_project(name="General", user_profile=user_profile, description="Default project")
        return projects[0]

_project_service: ProjectService | None = None

def get_project_service():
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
