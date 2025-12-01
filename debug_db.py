import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.services.vector_db import VectorDBService

async def main():
    print("Initializing VectorDBService...")
    db = VectorDBService()
    
    print("\n--- Listing Documents ---")
    # Get all documents (limit 20)
    # Use the project ID seen in previous logs: 27ebd40c-ca3a-4bfc-bb70-014075235787
    docs = await db.list_documents(project_id="27ebd40c-ca3a-4bfc-bb70-014075235787", limit=20)
    
    for doc in docs:
        print(f"\nSource ID: {doc['source_id']}")
        print(f"Filename (in list): {doc['filename']}")
        
        # Fetch full metadata for this ID
        print("Fetching full metadata from Chroma...")
        # FIX: Use where={"source_id": ...} instead of ids=[...]
        result = db.collection.get(where={"source_id": doc['source_id']}, include=["metadatas"])
        if result and result['metadatas']:
            print(f"Metadata: {result['metadatas'][0]}")
        else:
            print("No metadata found in direct get()")

if __name__ == "__main__":
    asyncio.run(main())
