import asyncio
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.vector_db import get_vector_db_service
from backend.services.rag import get_rag_service

async def main():
    vector_db = get_vector_db_service()
    rag = get_rag_service()
    
    # The project ID from the user's logs
    project_id = "27ebd40c-ca3a-4bfc-bb70-014075235787"
    
    print(f"--- Debugging Project: {project_id} ---")
    
    # 1. List documents
    print("\n1. Listing Documents:")
    docs = await vector_db.list_documents(project_id=project_id)
    for doc in docs:
        print(f" - {doc['filename']} (Source ID: {doc['source_id']})")
        
    if not docs:
        print("No documents found in this project.")
        return

    # 2. Raw Search for "objectives"
    query = "objectives"
    print(f"\n2. Raw Search for '{query}' (n_results=10):")
    results = await vector_db.search(query, project_id=project_id, n_results=10)
    
    if results and results['documents']:
        for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
            print(f"\n[Result {i+1}] Score: {results['distances'][0][i] if results['distances'] else 'N/A'}")
            print(f"Source: {meta.get('filename')} (Chunk {meta.get('chunk_index')})")
            print(f"Content Preview: {doc[:200]}...")
            print("-" * 50)
            
            # Check for "3.2" or "Objectives" specifically
            if "3.2" in doc or "Objectives" in doc:
                print(">>> FOUND '3.2' or 'Objectives' in this chunk! <<<")
    else:
        print("No results found.")

    # 3. Check specifically for "3.2 Objectives" string in ALL chunks (slow but thorough)
    print("\n3. Scanning ALL chunks for literal '3.2 Objectives'...")
    all_docs = vector_db.collection.get(where={"project_id": project_id})
    found_literal = False
    if all_docs and all_docs['documents']:
        for i, doc in enumerate(all_docs['documents']):
            if "3.2 Objectives" in doc or "3.2  Objectives" in doc: # Handle potential extra spaces
                print(f"\n>>> FOUND LITERAL MATCH in Chunk {all_docs['metadatas'][i].get('chunk_index')} of {all_docs['metadatas'][i].get('filename')} <<<")
                print(f"Content: {doc}")
                found_literal = True
    
    if not found_literal:
        print("Could not find literal string '3.2 Objectives' in any chunk.")

if __name__ == "__main__":
    asyncio.run(main())
