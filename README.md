# Local Testing Guide

Follow these steps to run the Dedup Agent on your local machine.

## Prerequisites
- Python 3.11+
- Node.js 18+
- Google Cloud SDK installed and configured.

## 1. Google Cloud Authentication
The app uses Vertex AI and BigQuery. You must authenticate your local environment:
```powershell
gcloud auth application-default login
gcloud config set project crown-cdw-intelia-dev
```

## 2. Backend Setup
Navigate to the `backend` directory and install dependencies:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Run the backend server:
```powershell
python main.py
```
The backend will be available at `http://localhost:8000`.

## 3. Frontend Setup
Navigate to the `frontend` directory and install dependencies:
```powershell
cd frontend
npm install
```

Run the development server:
```powershell
npm run dev
```
The frontend will be available at `http://localhost:3000`.

## 5. Understanding the Results


Here is how to interpret the output columns:

| Column | Description |
| :--- | :--- |
| **group_id** | Unique ID for a cluster of duplicates. All items with the same ID refer to the same product. |
| **match_type** | The logic used: `exact_item_code`, `exact_barcode`, `fuzzy_embedding`, or `llm_matched`. |
| **confidence** | Probability score (0.0 to 1.0). 1.0 for exact matches; cosine similarity for fuzzy matches. |
| **review_required** | If `True`, the match is border-line and appears in the Human Review Queue for final approval. |

### Match Types in Detail:
- **exact_item_code/barcode**: 100% matches based on unique identifiers.
- **fuzzy_embedding**: High-confidence matches found using AI vector similarity.
- **llm_matched**: Ambiguous cases where Gemini 2.0 Flash confirmed it's a match.
- **llm_discarded**: Potential matches that Gemini identified as different products (group_id will be cleared).
