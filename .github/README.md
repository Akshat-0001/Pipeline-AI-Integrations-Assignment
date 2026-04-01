# Pipeline AI Integrations Assignment

This is my submission for the integrations technical assessment.

## Video walkthrough
![Video walkthrough](frontend/public/video-walkthrough.gif)

## What is implemented
- HubSpot OAuth flow (backend + frontend)
- HubSpot item loading from contacts, companies, and deals
- HubSpot integration added to the UI selector and data loader

## Tech stack
- Frontend: React (JavaScript)
- Backend: FastAPI (Python)
- Cache/state: Redis

## Run locally
1. Start Redis
2. Start backend
3. Start frontend

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm start
```

## Environment variables
Create `backend/.env` and set:
- `HUBSPOT_CLIENT_ID`
- `HUBSPOT_CLIENT_SECRET`
- `HUBSPOT_SCOPES`



