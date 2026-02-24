from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv

from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="Dedup Agent API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Dedup Agent API is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

def get_bq_service():
    from services.bigquery_service import BigQueryService
    return BigQueryService()

def get_dedup_agent():
    from services.dedup_logic import DedupAgent
    return DedupAgent()

class DedupRequest(BaseModel):
    dataset_id: str
    table_id: str

@app.post("/api/dedup/trigger")
async def trigger_dedup(request: DedupRequest):
    try:
        print(f"Triggering dedup for {request.dataset_id}.{request.table_id}")
        bq_service = get_bq_service()
        dedup_agent = get_dedup_agent()
        
        df = bq_service.fetch_data(request.dataset_id, request.table_id)
        print(f"Data fetched: {len(df)} rows")
        result_df = dedup_agent.run(df)
        print(f"Deduplication complete: {len(result_df)} rows processed")
        
        # Persist results
        output_table = bq_service.update_dedup_results(request.dataset_id, request.table_id, result_df)
        
        response_data = {
            "status": "success", 
            "processed_count": len(result_df),
            "output_table": output_table,
            "v": "2.1" # Debug version
        }
        print(f"Returning response: {response_data}")
        return response_data
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print(f"ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/review/list")
async def get_review_list():
    # Return mock data for now
    return {"reviews": []}

@app.post("/api/review/decision")
async def submit_decision(decision: dict):
    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
