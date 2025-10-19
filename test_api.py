"""
Test script for BKW Hackathon API
Tests the step1 endpoint with sample Excel files
"""

import requests
import json
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
HEATING_FILE = "src/power/data/p5-lp2-input-heizung.xlsm"
VENTILATION_FILE = "src/power/data/p5-lp2-input-raumluftung.xlsm"


def test_health_check():
    """Test health check endpoint"""
    print("Testing health check...")
    response = requests.get(f"{API_BASE_URL}/healthz")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200


def test_step1_analysis():
    """Test step 1 analysis endpoint"""
    print("Testing Step 1 analysis...")
    
    # Check if files exist
    heating_path = Path(HEATING_FILE)
    ventilation_path = Path(VENTILATION_FILE)
    
    if not heating_path.exists():
        print(f"❌ Heating file not found: {HEATING_FILE}")
        return None
    
    if not ventilation_path.exists():
        print(f"❌ Ventilation file not found: {VENTILATION_FILE}")
        return None
    
    # Prepare files for upload
    files = {
        'file_heating': ('heating.xlsm', open(heating_path, 'rb'), 'application/vnd.ms-excel.sheet.macroEnabled.12'),
        'file_ventilation': ('ventilation.xlsm', open(ventilation_path, 'rb'), 'application/vnd.ms-excel.sheet.macroEnabled.12'),
    }
    
    data = {
        'project_name': 'Test Project',
        'auto_detect_structure': 'true',
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/analyze/step1",
            files=files,
            data=data,
            timeout=60,
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Analysis ID: {result['analysisId']}")
            print(f"✅ Total Rooms: {result['step1']['totalRooms']}")
            print(f"✅ Optimized Rooms: {result['step1']['optimizedRooms']}")
            print(f"✅ Improvement Rate: {result['step1']['improvementRate']}%")
            print(f"✅ Confidence: {result['step1']['confidence']}%")
            
            if result.get('processedExcelBase64'):
                excel_size = len(result['processedExcelBase64'])
                print(f"✅ Excel Base64 size: {excel_size} characters (~{excel_size // 1024}KB)")
                print(f"✅ Suggested filename: {result.get('processedExcelFilename')}")
            
            if result.get('details'):
                details = result['details']
                print(f"\nDetails:")
                print(f"  - Original room types: {details.get('originalRoomTypesCount')}")
                print(f"  - Optimized room types: {details.get('optimizedRoomTypesCount')}")
                print(f"  - Avg room size: {details.get('avgRoomSizeM2')} m²")
                print(f"  - Total area: {details.get('totalAreaM2')} m²")
            
            print()
            return result['analysisId']
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}\n")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}\n")
        return None
    finally:
        # Close file handles
        for file_tuple in files.values():
            if hasattr(file_tuple[1], 'close'):
                file_tuple[1].close()


def test_step2_analysis(analysis_id: str):
    """Test step 2 analysis endpoint"""
    print("Testing Step 2 analysis...")
    
    payload = {
        "analysisId": analysis_id,
        "parameters": {
            "pricePerKWh": 0.30,
        }
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/analyze/step2",
            json=payload,
            timeout=30,
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Energy Consumption: {result['step2']['energyConsumption']} W/m²")
            print(f"✅ Reduction: {result['step2']['reductionPercentage']}%")
            print(f"✅ Annual Savings: €{result['step2']['annualSavings']}")
            
            if result.get('details'):
                details = result['details']
                print(f"\nDetails:")
                print(f"  - Heating Power: {details.get('heatingPowerKw')} kW")
                print(f"  - Annual Consumption: {details.get('annualConsumptionKwh')} kWh")
                print(f"  - Savings: {details.get('savingsKwh')} kWh")
                
                if details.get('breakdownByRoomType'):
                    print(f"\n  Breakdown by room type:")
                    for room in details['breakdownByRoomType']:
                        print(f"    - {room['roomType']}: {room['wPerM2']} W/m² ({room.get('sharePercent', 0)}%)")
            
            print()
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}\n")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}\n")
        return False


def test_status(analysis_id: str):
    """Test status endpoint"""
    print("Testing status endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/status/{analysis_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ State: {result['state']}")
            print(f"✅ Step: {result.get('step')}")
            print(f"✅ Progress: {result.get('progressPercent')}%\n")
            return True
        else:
            print(f"❌ Error: {response.status_code}\n")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}\n")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("BKW Hackathon API Test Suite")
    print("=" * 60)
    print()
    
    # Test 1: Health check
    if not test_health_check():
        print("⚠️  API server may not be running. Start it with:")
        print("   python src/api.py")
        return
    
    # Test 2: Step 1 analysis
    analysis_id = test_step1_analysis()
    if not analysis_id:
        print("⚠️  Step 1 test failed. Check that:")
        print("   1. Files exist at the specified paths")
        print("   2. API server is running correctly")
        return
    
    # Test 3: Status check
    test_status(analysis_id)
    
    # Test 4: Step 2 analysis
    test_step2_analysis(analysis_id)
    
    print("=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
