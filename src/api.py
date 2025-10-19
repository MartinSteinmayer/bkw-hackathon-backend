"""
FastAPI Backend for BKW Hackathon
Provides endpoints for Excel analysis, room type optimization, and energy calculation
"""

import asyncio
import base64
import io
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import tempfile
import shutil

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import existing utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.power.merge_excel_files import merge_heating_ventilation_excel
from src.roomtypes.service import process as process_roomtypes
from src.roomtypes.models import Cfg

# ==================== Models ====================

class KeyChange(BaseModel):
    """Room type change"""
    model_config = ConfigDict(populate_by_name=True)
    
    from_type: str = Field(..., alias="from")
    to: str
    count: int


class Step1Details(BaseModel):
    """Step 1 detailed metrics"""
    originalRoomTypesCount: Optional[int] = None
    optimizedRoomTypesCount: Optional[int] = None
    avgRoomSizeM2: Optional[float] = None
    totalAreaM2: Optional[float] = None
    keyChanges: Optional[List[KeyChange]] = None


class Step1Data(BaseModel):
    """Step 1 core metrics"""
    optimizedRooms: int
    totalRooms: int
    improvementRate: float
    confidence: float


class Step1Response(BaseModel):
    """Step 1 response with analysis results"""
    analysisId: str
    processedExcelBase64: Optional[str] = None
    processedExcelFilename: Optional[str] = None
    step1: Step1Data
    details: Optional[Step1Details] = None


class Step2Request(BaseModel):
    """Step 2 request"""
    analysisId: str
    parameters: Optional[Dict] = None


class RoomTypeBreakdown(BaseModel):
    """Room type energy breakdown"""
    roomType: str
    wPerM2: float
    sharePercent: Optional[float] = None


class Step2Details(BaseModel):
    """Step 2 detailed metrics"""
    heatingPowerKw: Optional[float] = None
    annualConsumptionKwh: Optional[float] = None
    savingsKwh: Optional[float] = None
    breakdownByRoomType: Optional[List[RoomTypeBreakdown]] = None


class Step2Data(BaseModel):
    """Step 2 core metrics"""
    energyConsumption: float
    reductionPercentage: float
    annualSavings: float


class Step2Response(BaseModel):
    """Step 2 response"""
    step2: Step2Data
    details: Optional[Step2Details] = None


# ==================== In-Memory Storage (replace with Redis/DB for production) ====================

class AnalysisStore:
    """Simple in-memory store for analysis data"""
    
    def __init__(self):
        self._data: Dict[str, Dict] = {}
    
    def save(self, analysis_id: str, data: Dict):
        """Save analysis data"""
        self._data[analysis_id] = {
            **data,
            "created_at": datetime.now().isoformat(),
        }
    
    def get(self, analysis_id: str) -> Optional[Dict]:
        """Get analysis data"""
        return self._data.get(analysis_id)
    
    def exists(self, analysis_id: str) -> bool:
        """Check if analysis exists"""
        return analysis_id in self._data
    
    def delete(self, analysis_id: str):
        """Delete analysis data"""
        if analysis_id in self._data:
            del self._data[analysis_id]


analysis_store = AnalysisStore()

# ==================== Configuration ====================

class Config:
    """Application configuration from environment variables"""
    GOOGLE_GEMINI_API_KEY: str = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PORT: int = int(os.getenv("PORT", "10000"))  # Render uses PORT env var
    HOST: str = os.getenv("HOST", "0.0.0.0")
    RELOAD: bool = os.getenv("RELOAD", "false").lower() == "true"  # Disable reload in production
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        # Check if at least one API key is set
        if not cls.GOOGLE_GEMINI_API_KEY and not cls.GEMINI_API_KEY:
            print("⚠️  WARNING: No Gemini API key found in environment variables!")
            print("   Please set GOOGLE_GEMINI_API_KEY or GEMINI_API_KEY in your .env file")
            print("   AI-powered structure detection will not work without an API key.")
            print()
        else:
            print(f"✅ Gemini API key loaded successfully")
        
        return True


config = Config()

# ==================== FastAPI App ====================

app = FastAPI(
    title="BKW Hackathon API",
    description="Building energy analysis and optimization API",
    version="1.0.0",
)

# CORS middleware - UPDATE for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        os.getenv("FRONTEND_URL", "*")  # Add your frontend URL as env var
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Startup Event ====================

@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup"""
    print("\n" + "=" * 60)
    print("🚀 BKW Hackathon API Starting...")
    print("=" * 60)
    config.validate()
    print(f"📍 Server: http://{config.HOST}:{config.PORT}")
    print(f"📚 API Docs: http://{config.HOST}:{config.PORT}/docs")
    print(f"📖 ReDoc: http://{config.HOST}:{config.PORT}/redoc")
    print("=" * 60 + "\n")


# ==================== Helper Functions ====================

def df_to_base64_excel(df: pd.DataFrame) -> str:
    """Convert DataFrame to base64 encoded Excel file"""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Merged Data')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


async def save_uploaded_file(upload_file: UploadFile, suffix: str = ".xlsx") -> Path:
    """Save uploaded file to temporary location"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(temp_file.name)
    
    try:
        content = await upload_file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        return temp_path
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e


def calculate_room_metrics(df: pd.DataFrame) -> Dict:
    """Calculate room-related metrics from merged DataFrame"""
    # Common column names for room identification
    room_cols = ['Geschoss', 'Raum-Nr.', 'Raum-Bezeichnung', 'Nummer Raumtyp']
    
    # Filter valid rooms (at least room number exists)
    if 'Raum-Nr.' in df.columns:
        valid_rooms = df[df['Raum-Nr.'].notna()]
        total_rooms = len(valid_rooms)
    else:
        total_rooms = len(df)
        valid_rooms = df
    
    # Calculate area metrics
    area_col = None
    for col in ['Fläche', 'Fläche_heating', 'Flaeche']:
        if col in df.columns:
            area_col = col
            break
    
    if area_col:
        total_area = float(valid_rooms[area_col].sum())
        avg_area = float(valid_rooms[area_col].mean())
    else:
        total_area = 0.0
        avg_area = 0.0
    
    # Count unique room types
    roomtype_col = None
    for col in ['Nummer Raumtyp', 'Raumtyp', 'Bezeichnung Raumtyp']:
        if col in df.columns:
            roomtype_col = col
            break
    
    if roomtype_col:
        unique_roomtypes = int(valid_rooms[roomtype_col].nunique())
    else:
        unique_roomtypes = 0
    
    return {
        'total_rooms': total_rooms,
        'total_area': total_area,
        'avg_area': avg_area,
        'unique_roomtypes': unique_roomtypes,
    }


# ==================== Endpoints ====================

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/analyze/step1", response_model=Step1Response)
async def analyze_step1(
    file_heating: UploadFile = File(..., description="Heating/Cooling Excel file (KLT/HZG)"),
    file_ventilation: UploadFile = File(..., description="Ventilation Excel file (RLT)"),
    project_name: Optional[str] = Form(None),
    auto_detect_structure: bool = Form(True),
    header_row: Optional[int] = Form(None),
):
    """
    Step 1: Upload and merge Excel files, optimize room types
    
    Accepts:
    - file_heating: Excel file for heating/cooling (.xls, .xlsx, .xlsm)
    - file_ventilation: Excel file for ventilation (.xls, .xlsx, .xlsm)
    - project_name: Optional project name
    - auto_detect_structure: Use AI to detect Excel structure (default: True)
    - header_row: Manual header row number if auto_detect_structure=False
    
    Returns:
    - analysisId: Unique ID for subsequent API calls
    - processedExcelBase64: Base64 encoded merged Excel file
    - step1: Core metrics (rooms, improvement rate, confidence)
    - details: Additional metrics and changes
    """
    
    # Validate file types
    allowed_extensions = ['.xls', '.xlsx', '.xlsm']
    
    def validate_filename(filename: str) -> bool:
        return any(filename.lower().endswith(ext) for ext in allowed_extensions)
    
    if not validate_filename(file_heating.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid heating file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    if not validate_filename(file_ventilation.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ventilation file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Generate analysis ID
    analysis_id = str(uuid.uuid4())
    
    # Save uploaded files temporarily
    heating_path = None
    ventilation_path = None
    
    try:
        # Determine file extension
        heating_suffix = Path(file_heating.filename).suffix
        ventilation_suffix = Path(file_ventilation.filename).suffix
        
        heating_path = await save_uploaded_file(file_heating, suffix=heating_suffix)
        ventilation_path = await save_uploaded_file(file_ventilation, suffix=ventilation_suffix)
        
        # Merge Excel files using existing utility
        merged_df = await merge_heating_ventilation_excel(
            str(heating_path),
            str(ventilation_path),
            header_row=header_row,
            auto_detect_structure=auto_detect_structure,
            how='outer',
        )
        
        # Calculate metrics
        metrics = calculate_room_metrics(merged_df)
        
        # Convert merged DataFrame to base64
        excel_base64 = df_to_base64_excel(merged_df)
        suggested_filename = f"merged_analysis_{analysis_id[:8]}.xlsx"
        
        # Simulate room type optimization
        # In production, integrate actual room type optimization logic
        total_rooms = metrics['total_rooms']
        optimized_rooms = int(total_rooms * 0.90)  # 90% optimization rate
        improvement_rate = 90.0
        confidence = 98.0
        
        # Prepare response
        step1_data = Step1Data(
            optimizedRooms=optimized_rooms,
            totalRooms=total_rooms,
            improvementRate=improvement_rate,
            confidence=confidence,
        )
        
        details = Step1Details(
            originalRoomTypesCount=metrics['unique_roomtypes'],
            optimizedRoomTypesCount=max(metrics['unique_roomtypes'] - 5, 1),
            avgRoomSizeM2=round(metrics['avg_area'], 1),
            totalAreaM2=round(metrics['total_area'], 0),
            keyChanges=[
                KeyChange(**{"from": "Büro Standard", "to": "Büro Optimiert", "count": 5}),
                KeyChange(**{"from": "Konferenzraum Groß", "to": "Konferenzraum Optimiert", "count": 3}),
            ]
        )
        
        # Store analysis data for step 2
        analysis_store.save(analysis_id, {
            "merged_df": merged_df.to_dict(),
            "metrics": metrics,
            "project_name": project_name or "Unnamed Project",
            "step1_data": step1_data.model_dump(),
            "details": details.model_dump(),
        })
        
        response = Step1Response(
            analysisId=analysis_id,
            processedExcelBase64=excel_base64,
            processedExcelFilename=suggested_filename,
            step1=step1_data,
            details=details,
        )
        
        return response
        
    except Exception as e:
        # Clean up temporary files
        if heating_path and heating_path.exists():
            heating_path.unlink()
        if ventilation_path and ventilation_path.exists():
            ventilation_path.unlink()
        
        raise HTTPException(
            status_code=422,
            detail=f"Failed to process Excel files: {str(e)}"
        )
    
    finally:
        # Clean up temporary files
        if heating_path and heating_path.exists():
            try:
                heating_path.unlink()
            except:
                pass
        if ventilation_path and ventilation_path.exists():
            try:
                ventilation_path.unlink()
            except:
                pass


@app.post("/api/analyze/step2", response_model=Step2Response)
async def analyze_step2(request: Step2Request):
    """
    Step 2: Energy consumption and cost analysis
    
    Accepts:
    - analysisId: ID from step 1
    - parameters: Optional parameters (pricePerKWh, climateZone, etc.)
    
    Returns:
    - step2: Energy metrics (consumption, savings, reduction %)
    - details: Detailed breakdown by room type
    """
    
    # Check if analysis exists
    if not analysis_store.exists(request.analysisId):
        raise HTTPException(
            status_code=404,
            detail=f"Analysis ID not found: {request.analysisId}"
        )
    
    # Get stored data
    analysis_data = analysis_store.get(request.analysisId)
    
    try:
        # In production, implement actual energy calculation here
        # For now, return simulated data
        
        step2_data = Step2Data(
            energyConsumption=45.0,  # W/m²
            reductionPercentage=18.0,
            annualSavings=7800.0,  # €
        )
        
        details = Step2Details(
            heatingPowerKw=57.0,
            annualConsumptionKwh=143820.0,
            savingsKwh=25680.0,
            breakdownByRoomType=[
                RoomTypeBreakdown(roomType="Büros", wPerM2=42.0, sharePercent=40.0),
                RoomTypeBreakdown(roomType="Konferenzräume", wPerM2=55.0, sharePercent=25.0),
                RoomTypeBreakdown(roomType="Gemeinschaftsbereiche", wPerM2=38.0, sharePercent=20.0),
                RoomTypeBreakdown(roomType="Flure & Technik", wPerM2=28.0, sharePercent=15.0),
            ]
        )
        
        # Update stored data with step2 results
        analysis_data["step2_data"] = step2_data.model_dump()
        analysis_data["step2_details"] = details.model_dump()
        analysis_store.save(request.analysisId, analysis_data)
        
        return Step2Response(
            step2=step2_data,
            details=details,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate energy metrics: {str(e)}"
        )


@app.get("/api/status/{analysis_id}")
async def get_status(analysis_id: str):
    """
    Get analysis status (for async processing)
    """
    if not analysis_store.exists(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    analysis_data = analysis_store.get(analysis_id)
    
    # Determine completion state
    has_step1 = "step1_data" in analysis_data
    has_step2 = "step2_data" in analysis_data
    
    if has_step2:
        state = "completed"
        step = "report"
    elif has_step1:
        state = "completed"
        step = "step1"
    else:
        state = "processing"
        step = None
    
    return {
        "analysisId": analysis_id,
        "state": state,
        "step": step,
        "progressPercent": 100 if state == "completed" else 50,
    }


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    
    # Validate config before starting
    config.validate()
    
    uvicorn.run(
        "src.api:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD
    )
