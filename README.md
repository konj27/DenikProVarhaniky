# Varhanici Log Page (Streamlit + FastAPI + sqlite3)

A lightweight full-stack Python starter template using:
- **Frontend**: [Streamlit](https://streamlit.io/) (`frontend/app.py`)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (`backend/main.py`, `backend/models.py`, `backend/schemas.py`)
- **Database / Persistence**: Built-in Python `sqlite3` (`backend/database.py`)

## Project Structure

```text
varhanici_logPage/
├── backend/
│   ├── __init__.py
│   ├── database.py    # Standard sqlite3 connection and table initialization
│   ├── main.py        # FastAPI route endpoints delegating to models.py
│   ├── models.py      # Endpoint handler functions returning Pydantic response models
│   └── schemas.py     # Pydantic request schemas and response models
├── frontend/
│   └── app.py         # Streamlit UI
├── .gitignore
├── requirements.txt
└── README.md
```

## Quickstart

### 1. Create a virtual environment and install dependencies

```powershell
cd varhanici_logPage
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run the FastAPI Backend

In your first terminal (from the `varhanici_logPage` repository root):

```powershell
uvicorn backend.main:app --reload --port 8000
```

- Interactive Swagger UI docs: `http://127.0.0.1:8000/docs`
- SQLite database file (`app.db`) is automatically initialized on startup.

### 3. Run the Streamlit Frontend

In a second terminal (with the virtual environment activated):

```powershell
streamlit run frontend/app.py
```

- Opens in your browser at `http://localhost:8501`
