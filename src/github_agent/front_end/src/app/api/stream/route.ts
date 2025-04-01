import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const requestId = crypto.randomUUID();
    
    console.log(`[${requestId}] Stream request received`);
    
    // Forward the request to the FastAPI backend
    const backendUrl = `${process.env.BACKEND_URL || 'http://localhost:8000'}/stream`;
    console.log(`[${requestId}] Forwarding to backend: ${backendUrl}`);
    
    let backendResponse;
    try {
      backendResponse = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': requestId,
        },
        body: JSON.stringify(body),
      });
    } catch (fetchError) {
      console.error(`[${requestId}] Backend connection error:`, fetchError);
      return new Response(
        JSON.stringify({
          error: 'Failed to connect to backend server',
          message: 'Is the Python FastAPI backend running on port 8000?',
          details: fetchError instanceof Error ? fetchError.message : String(fetchError),
          code: (fetchError as any).code,
        }),
        {
          status: 503, // Service Unavailable
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    if (!backendResponse.ok) {
      throw new Error(`Backend returned ${backendResponse.status}: ${await backendResponse.text()}`);
    }

    // Create a TransformStream to relay the streaming response
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    
    // Stream the response from the backend to the client
    const reader = backendResponse.body?.getReader();
    if (!reader) {
      throw new Error('Failed to get reader from response');
    }
    
    const pump = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            console.log(`[${requestId}] Stream complete`);
            await writer.close();
            break;
          }
          await writer.write(value);
        }
      } catch (e) {
        console.error(`[${requestId}] Error in stream:`, e);
        await writer.close();
      }
    };
    
    // Start pumping the data without awaiting
    pump();
    
    // Return the readable side of the transform stream
    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no', // Prevents Nginx from buffering the response
      },
    });
  } catch (error) {
    console.error('Error handling stream request:', error);
    return new Response(
      JSON.stringify({ 
        error: 'Failed to process request',
        details: error instanceof Error ? error.message : String(error)
      }),
      { 
        status: 500,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  }
}

// Prevent GET requests to this endpoint
export async function GET() {
  return new Response(
    JSON.stringify({ error: 'Method not allowed. Use POST instead.' }),
    { 
      status: 405,
      headers: {
        'Content-Type': 'application/json',
        'Allow': 'POST'
      },
    }
  );
}
