import os
import sys
from openai import OpenAI

def test_vertex():
    vertex_project_id = os.getenv("VERTEX_PROJECT_ID")
    vertex_location = os.getenv("VERTEX_LOCATION") or "us-central1"
    
    print(f"Testing Vertex AI integration for project: {vertex_project_id}")
    print(f"Location: {vertex_location}")
    
    if not vertex_project_id:
        print("ERROR: VERTEX_PROJECT_ID not set")
        sys.exit(1)
        
    try:
        import google.auth
        from google.auth.transport.requests import Request
        credentials, project_id = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        credentials.refresh(Request())
        
        base_url = f"https://{vertex_location}-aiplatform.googleapis.com/v1beta1/projects/{vertex_project_id}/locations/{vertex_location}/endpoints/openapi"
        
        client = OpenAI(
            api_key=credentials.token,
            base_url=base_url,
        )
        
        print("Sending 'hello' to gemini-1.5-flash-001...")
        response = client.chat.completions.create(
            model="gemini-1.5-flash-001",
            messages=[{"role": "user", "content": "Hello, this is a test. Reply with 'vertex success'."}],
            temperature=0.0
        )
        
        print("\nSUCCESS! Response from model:")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_vertex()
