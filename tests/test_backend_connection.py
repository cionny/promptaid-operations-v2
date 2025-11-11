"""
Test script to verify backend connection before running Streamlit
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.backend_client import get_backend_client


async def test_backend():
    """Test the backend client with a simple query"""
    
    print("🧪 Testing Backend Client Connection\n")
    print("=" * 60)
    
    client = get_backend_client()
    query = "Quali fiumi sono in piena in Liguria?"
    
    print(f"\n📝 Query: {query}\n")
    print("🔄 Processing...\n")
    
    metadata = None
    response = ""
    artifacts = []
    
    try:
        async for chunk in client.process_query_stream(
            query=query,
            enabled_agents=["MeteoAgent"],
            llm_tool_calling=False,
            llm_summaries=False
        ):
            if chunk["type"] == "metadata":
                metadata = chunk["data"]
                print("✅ Metadata received:")
                print(f"   Agent: {metadata['agent']}")
                print(f"   Tool: {metadata['tool']}")
                print(f"   Mode: {metadata['mode']}")
                print(f"   Params: {metadata['extracted_params']}")
                print()
            
            elif chunk["type"] == "response_chunk":
                response += chunk["data"]["text"]
                # Print without newline for streaming effect
                print(chunk["data"]["text"], end="", flush=True)
            
            elif chunk["type"] == "response_end":
                print("\n")
            
            elif chunk["type"] == "artifacts":
                artifacts = chunk["data"]
                print(f"📎 Artifacts: {len(artifacts)} items")
                for art in artifacts:
                    if art["type"] == "link":
                        print(f"   🔗 {art['name']}")
                    elif art["type"] == "table":
                        print(f"   📊 {art['name']} - {len(art['data'])} rows")
            
            elif chunk["type"] == "error":
                print(f"❌ Error: {chunk['data']['message']}")
                return False
        
        print("\n" + "=" * 60)
        print("✅ Backend test completed successfully!")
        return True
    
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_backend())
    sys.exit(0 if success else 1)
