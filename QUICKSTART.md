# Quick Start Guide - API Endpoint

## 🚀 Get the API Running in 3 Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- FastAPI (web framework)
- Uvicorn (ASGI server)
- python-multipart (file upload support)
- Pydantic (data validation)

### Step 2: Start the Server
```bash
python3 src/api.py
```

✅ Server runs on: http://localhost:8000  
✅ API docs: http://localhost:8000/docs

### Step 3: Test It
```bash
python3 test_api.py
```

This will:
1. Check health endpoint
2. Upload sample .xlsm files
3. Get analysis results with base64 Excel
4. Test step 2 endpoint

## 📝 What You Get Back

```json
{
  "analysisId": "abc-123-def",
  "processedExcelBase64": "UEsDBBQABgAI...",  // ← Download this!
  "processedExcelFilename": "merged_analysis_abc123.xlsx",
  "step1": {
    "optimizedRooms": 47,
    "totalRooms": 52,
    "improvementRate": 90,
    "confidence": 98
  }
}
```

## 🔗 Connect to Frontend

Your `api.ts` is already configured! Just make sure:

1. **Backend is running**: `python3 src/api.py`
2. **Frontend is running**: `cd bkw-ui && npm run dev`
3. **Upload files**: The UI will automatically call your API

The frontend's `downloadBase64Excel()` function will handle the base64 Excel download.

## 🧪 Manual Test with curl

```bash
curl -X POST "http://localhost:8000/api/analyze/step1" \
  -F "file_heating=@src/power/data/p5-lp2-input-heizung.xlsm" \
  -F "file_ventilation=@src/power/data/p5-lp2-input-raumluftung.xlsm" \
  -F "project_name=My Test Project" \
  | jq '.'
```

## 📚 Full Documentation

- **API_README.md** - Complete API documentation
- **INTEGRATION_GUIDE.md** - Frontend integration
- **IMPLEMENTATION_SUMMARY.md** - Technical details
- **http://localhost:8000/docs** - Interactive API docs

## ✅ What's Implemented

- [x] POST /api/analyze/step1 with .xlsm support
- [x] Base64 Excel encoding in response
- [x] POST /api/analyze/step2 for energy analysis
- [x] GET /api/status/:id for status checks
- [x] GET /healthz for health checks
- [x] CORS enabled for frontend
- [x] Error handling and validation
- [x] Automatic file cleanup

## 🎯 Next Actions

1. **Install & run** (see above)
2. **Test with sample files** (automated test script)
3. **Connect frontend** (it's already configured!)
4. **Optional**: Enhance with real optimization logic

That's it! Your endpoint is ready to receive Excel files and return base64 encoded results. 🎉
