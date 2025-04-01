import { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    // Extract parameters from URL path instead of using params
    const url = new URL(request.url);
    const pathParts = url.pathname.split('/').filter(Boolean);
    
    // Path format should be: api/file/{session_id}/{repo_name}/{file_path}
    // Remove "api" and "file" from the path parts
    const relevantParts = pathParts.slice(2);  // Skip "api" and "file"
    
    if (relevantParts.length < 2) {
      return Response.json({ error: 'Invalid URL format' }, { status: 400 });
    }
    
    const sessionId = relevantParts[0];
    const repoName = relevantParts[1];
    const filePath = relevantParts.slice(2).join('/');
    
    console.log(`Accessing: session=${sessionId}, repo=${repoName}, file=${filePath}`);
    
    // Forward the request to the FastAPI backend
    const backendUrl = `${process.env.BACKEND_URL || 'http://localhost:8000'}/file/${sessionId}/${repoName}/${filePath}`;
    
    console.log(`Fetching file from backend: ${backendUrl}`);
    const backendResponse = await fetch(backendUrl, {
      headers: {
        'Accept': 'application/json',
        'Cache-Control': 'no-cache'
      },
    });
    
    if (!backendResponse.ok) {
      console.error(`Backend returned error: ${backendResponse.status} ${backendResponse.statusText}`);
      return Response.json({ 
        error: `Backend error: ${backendResponse.status} ${backendResponse.statusText}` 
      }, { status: backendResponse.status });
    }
    
    const data = await backendResponse.json();
    
    // Check if the backend returned an error
    if (data && data.error) {
      console.error(`Error from backend: ${data.error}`);
      return Response.json({ error: data.error }, { status: 400 });
    }
    
    // Return the response
    return Response.json(data);
  } catch (error) {
    console.error('Error fetching file:', error);
    return Response.json({ error: `Failed to fetch file content: ${error.message}` }, { status: 500 });
  }
}
