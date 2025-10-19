# BKW Hackathon API

FastAPI backend for building energy analysis and optimization.

## Features

- **Step 1**: Upload and merge Excel files (heating/ventilation), optimize room types
- **Step 2**: Calculate energy consumption and cost savings
- Base64 encoded Excel output for easy frontend download
- Support for `.xls`, `.xlsx`, and `.xlsm` files

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_GEMINI_API_KEY=your_api_key_here
```

### 3. Run the API Server

```bash
# Development mode (auto-reload)
python src/api.py

# Or using uvicorn directly
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

### 4. View API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### POST /api/analyze/step1

Upload two Excel files for analysis.

**Request:**
- `file_heating`: Excel file (KLT/HZG)
- `file_ventilation`: Excel file (RLT)
- `project_name` (optional): Project name
- `auto_detect_structure` (optional, default: true): Use AI structure detection
- `header_row` (optional): Manual header row number

**Response:**
```json
{
  "analysisId": "f1d2d2f9-7c3e-4a1a-9a67-5f2d9b1b2a30",
  "processedExcelBase64": "UEsDBBQABgAIAAAAIQ...",
  "processedExcelFilename": "merged_analysis_f1d2d2f9.xlsx",
  "step1": {
    "optimizedRooms": 47,
    "totalRooms": 52,
    "improvementRate": 90,
    "confidence": 98
  },
  "details": {
    "originalRoomTypesCount": 52,
    "optimizedRoomTypesCount": 47,
    "avgRoomSizeM2": 24.5,
    "totalAreaM2": 1274,
    "keyChanges": [
      { "from": "Büro Standard", "to": "Büro Optimiert", "count": 5 }
    ]
  }
}
```

### POST /api/analyze/step2

Calculate energy consumption and savings.

**Request:**
```json
{
  "analysisId": "f1d2d2f9-7c3e-4a1a-9a67-5f2d9b1b2a30",
  "parameters": {
    "pricePerKWh": 0.30
  }
}
```

**Response:**
```json
{
  "step2": {
    "energyConsumption": 45,
    "reductionPercentage": 18,
    "annualSavings": 7800
  },
  "details": {
    "heatingPowerKw": 57,
    "annualConsumptionKwh": 143820,
    "savingsKwh": 25680,
    "breakdownByRoomType": [
      { "roomType": "Büros", "wPerM2": 42, "sharePercent": 40 }
    ]
  }
}
```

### GET /api/status/:analysisId

Check analysis status.

**Response:**
```json
{
  "analysisId": "f1d2d2f9-...",
  "state": "completed",
  "step": "step1",
  "progressPercent": 100
}
```

### GET /healthz

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-10-19T12:34:56"
}
```

## Testing

### Test with curl

```bash
# Health check
curl http://localhost:8000/healthz

# Upload files (Step 1)
curl -X POST "http://localhost:8000/api/analyze/step1" \
  -F "file_heating=@path/to/heating.xlsm" \
  -F "file_ventilation=@path/to/ventilation.xlsm" \
  -F "project_name=Test Project"

# Step 2 (use analysisId from step 1 response)
curl -X POST "http://localhost:8000/api/analyze/step2" \
  -H "Content-Type: application/json" \
  -d '{"analysisId": "your-analysis-id-here"}'
```

### Test with Python script

See `test_api.py` for a complete test script.

## Frontend Integration

Update your Next.js API endpoint in `bkw-ui/next.config.ts`:

```typescript
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://localhost:8000/api/:path*',
    },
  ];
}
```

Or update the fetch URLs in `bkw-ui/src/services/api.ts` to point to `http://localhost:8000`.

## Production Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

- `GOOGLE_GEMINI_API_KEY`: Required for AI-powered structure detection
- `PORT`: API server port (default: 8000)

### Notes for Production

1. Replace in-memory `AnalysisStore` with Redis or database
2. Add authentication/authorization
3. Configure CORS for specific origins
4. Add rate limiting
5. Set up proper logging and monitoring
6. Use a production ASGI server (e.g., Gunicorn + Uvicorn workers)

## Architecture

```
Frontend (Next.js)
    ↓ HTTP/JSON
Backend API (FastAPI)
    ↓
├── merge_excel_files.py (Excel merging with AI structure detection)
├── roomtypes/service.py (Room type optimization)
├── costestimator/ (Cost calculations)
└── power/ (Energy calculations)
```

## Troubleshooting

### Import errors
```bash
# Make sure you're in the project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Port already in use
```bash
# Change the port
uvicorn src.api:app --port 8001
```

### Excel parsing errors
- Ensure files are valid Excel format (.xls, .xlsx, .xlsm)
- Check that files contain expected columns (Geschoss, Raum-Nr., etc.)
- Try with `auto_detect_structure=true` if manual header row fails
