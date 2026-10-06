# Need2Get — Complete MVP V4

Need2Get is a real-world availability product: understand a user's need, find local inventory, verify/confirm it, lock the stock, protect the trip, and confirm successful acquisition.

## Included end-to-end
1. Text search
2. Search suggestions
3. Voice search
4. Camera input
5. GPS permission
6. Distance/ETA
7. Merchant confirmation
8. Transactional stock lock
9. Two-customer competition protection
10. Journey tracking with live GPS updates
11. OTP completion + QR-ready flow
12. Stock failure + alternative inventory rerouting

## Important engineering note
The browser camera feature is implemented as a local visual demo (dominant-color signal). Exact object/material/size recognition requires a vision model/API. The backend endpoint is ready to replace with a production vision service.

The QR/OTP completion uses a secure reservation OTP in this local MVP. A production merchant app can render the same reservation payload as a QR and scan it at arrival.

## Run locally

Backend:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Frontend:
```powershell
cd frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500/`.

## Test the complete flow
Search `15 inch blue pipe`.
Request an item.
Merchant confirmation appears in the Merchant Confirmation panel.
Confirm it.
Start protected journey.
Allow GPS if desired.
Use Stock failure to see alternative inventory.
Use the OTP from the reservation to complete acquisition.

## GitHub
This project contains a frontend and FastAPI backend. GitHub Pages can host the static frontend, but it cannot run the Python backend. For a public working app, deploy the backend to a Python-capable host and change `API` in `frontend/app.js` from localhost to the deployed backend URL.

For a portfolio repository, keep the README, screenshots, architecture, API, and demo instructions. Do not commit secrets or API keys.
