import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.project import get_project_service
from backend.services.ingestion import get_ingestion_service
from backend.services.vector_db import get_vector_db_service
from backend.services.memory import get_memory_service
from backend.domain.models import Message, MessageRole
import structlog

# Configure logging
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(),
)

async def verify_project_isolation():
    print("🚀 Starting Project Isolation Verification...")
    
    # Initialize services
    project_service = get_project_service()
    ingestion_service = get_ingestion_service()
    vector_db = get_vector_db_service()
    memory = get_memory_service()
    
    # 1. Create Projects
    print("\n1️⃣  Creating Projects...")
    project_a = await project_service.create_project(name="Project A", user_profile="test_user")
    project_b = await project_service.create_project(name="Project B", user_profile="test_user")
    print(f"✅ Created Project A: {project_a.project_id}")
    print(f"✅ Created Project B: {project_b.project_id}")
    
    # 2. Ingest Document to Project A
    print("\n2️⃣  Ingesting Document to Project A...")
    # Create a dummy file
    with open("test_doc_a.txt", "w") as f:
        f.write("This is a secret document belonging to Project A. Project B should not see this.")
        
    try:
        source_id = await ingestion_service.process_file(
            file_path=os.path.abspath("test_doc_a.txt"),
            user_profile="test_user",
            project_id=project_a.project_id,
            metadata={"original_filename": "test_doc_a.txt"}
        )
        print(f"✅ Ingested document to Project A: {source_id}")
    finally:
        if os.path.exists("test_doc_a.txt"):
            os.remove("test_doc_a.txt")

    # 3. Verify Document Visibility
    print("\n3️⃣  Verifying Document Visibility...")
    docs_a = await vector_db.list_documents(project_id=project_a.project_id)
    docs_b = await vector_db.list_documents(project_id=project_b.project_id)
    
    print(f"Project A Docs: {len(docs_a)}")
    print(f"Project B Docs: {len(docs_b)}")
    
    if len(docs_a) == 1 and len(docs_b) == 0:
        print("✅ Document isolation SUCCESS: Project A has doc, Project B has none.")
    else:
        print("❌ Document isolation FAILED!")
        return

    # 4. Create Conversations
    print("\n4️⃣  Creating Conversations...")
    conv_a = await memory.create_conversation(user_profile="test_user", project_id=project_a.project_id, first_message="Hello Project A")
    conv_b = await memory.create_conversation(user_profile="test_user", project_id=project_b.project_id, first_message="Hello Project B")
    
    # 5. Verify Conversation Visibility
    print("\n5️⃣  Verifying Conversation Visibility...")
    chats_a = await memory.get_recent_conversations(user_profile="test_user", project_id=project_a.project_id)
    chats_b = await memory.get_recent_conversations(user_profile="test_user", project_id=project_b.project_id)
    
    print(f"Project A Chats: {len(chats_a)}")
    print(f"Project B Chats: {len(chats_b)}")
    
    # Note: get_recent_conversations might return multiple if run multiple times, but we check if they contain the correct IDs
    ids_a = [c.conversation_id for c in chats_a]
    ids_b = [c.conversation_id for c in chats_b]
    
    if conv_a.conversation_id in ids_a and conv_b.conversation_id not in ids_a:
        print("✅ Chat isolation SUCCESS: Project A sees its chat, but not B's.")
    else:
        print("❌ Chat isolation FAILED for Project A!")
        
    if conv_b.conversation_id in ids_b and conv_a.conversation_id not in ids_b:
        print("✅ Chat isolation SUCCESS: Project B sees its chat, but not A's.")
    else:
        print("❌ Chat isolation FAILED for Project B!")

    # Cleanup
    print("\n🧹 Cleaning up...")
    await project_service.delete_project(project_a.project_id)
    await project_service.delete_project(project_b.project_id)
    # Note: We should also delete documents and chats, but for now this is enough verification
    
    print("\n🎉 Verification Complete!")

if __name__ == "__main__":
    # Need to connect to DB first
    from backend.database import db
    
    async def main():
        await db.connect()
        await verify_project_isolation()
        await db.close()
        
    asyncio.run(main())
