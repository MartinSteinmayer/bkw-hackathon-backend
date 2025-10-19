# Frontend-Backend Integration Guide

## Option 1: Using Next.js Rewrites (Recommended for Development)

Create or update `bkw-ui/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
```

With this configuration, your frontend API calls to `/api/analyze/step1` will automatically proxy to `http://localhost:8000/api/analyze/step1`.

## Option 2: Environment Variables

Create `bkw-ui/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Update `bkw-ui/src/services/api.ts`:

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export async function fetchStep1Analysis(file1: File, file2: File): Promise<Step1Response> {
  const formData = new FormData();
  formData.append('file_heating', file1);
  formData.append('file_ventilation', file2);

  const response = await fetch(`${API_BASE_URL}/api/analyze/step1`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Upload failed' }));
    throw new Error(error.message || `Upload failed with status ${response.status}`);
  }

  return response.json();
}
```

## Running Both Servers

### Terminal 1: Backend API
```bash
# From project root
python src/api.py
# API will run on http://localhost:8000
```

### Terminal 2: Frontend
```bash
cd bkw-ui
npm run dev
# Frontend will run on http://localhost:3000
```

## Testing the Integration

1. Start both servers
2. Open http://localhost:3000 in your browser
3. Upload the two Excel files (.xlsm supported!)
4. The frontend should:
   - Call the backend API
   - Receive the analysis results
   - Download the merged Excel file (base64 decoded)

## CORS Configuration

The backend API already has CORS enabled for all origins during development:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, update this to specific origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Production Deployment

### Backend (FastAPI)
- Deploy to: Heroku, Railway, Render, AWS Lambda, Google Cloud Run
- Environment variables: `GOOGLE_GEMINI_API_KEY`
- Use production ASGI server (Gunicorn + Uvicorn)

### Frontend (Next.js)
- Deploy to: Vercel, Netlify, AWS Amplify
- Update API URL in environment variables
- Configure CORS on backend to allow your frontend domain

### Example Production Setup

**Backend (Dockerfile):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend (.env.production):**
```env
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.com
```
