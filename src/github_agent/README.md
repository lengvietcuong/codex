# GitHub Scrape Agent

This project consists of a Next.js frontend and a FastAPI backend that work together to provide an AI-assisted GitHub code exploration tool.

## Setup Instructions

### Prerequisites

- Python 3.8+
- Node.js 18+
- npm or yarn

### Backend Setup

1. Navigate to the project root directory:

```bash
cd /d:/scrape_github_agent
```

2. Create and activate a Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required Python packages:

```bash
pip install -r requirements.txt
```

4. Run the FastAPI backend server:

```bash
python agent/api.py
```

The backend server will start on http://localhost:8000.

### Frontend Setup

1. Navigate to the frontend directory:

```bash
cd /d:/scrape_github_agent/front_end
```

2. Install the required npm packages:

```bash
npm install
# or
yarn install
```

3. Run the Next.js development server:

```bash
npm run dev
# or
yarn dev
```

The frontend will be available at http://localhost:3000.

## Environment Variables

You may need to set up environment variables for API keys and other configurations.
Create a `.env` file in the project root directory:

```
BACKEND_URL=http://localhost:8000
# Add other environment variables as needed
```

## Troubleshooting

### Connection Refused Error

If you see a "Failed to connect to backend server" error in the frontend:

1. Make sure the Python backend is running with `python api.py`
2. Check that it's running on port 8000
3. Verify there are no firewall issues blocking localhost connections

### Other Common Issues

- If the frontend can't find the backend, check that `BACKEND_URL` is set correctly
- Ensure all dependencies are installed for both frontend and backend

## Architecture

The project consists of:

1. **FastAPI Backend**: Provides the API endpoints and handles the code agent logic
2. **Next.js Frontend**: Provides the user interface for interacting with the code agent

Communication between frontend and backend happens through RESTful API calls and Server-Sent Events (SSE) for streaming responses.
