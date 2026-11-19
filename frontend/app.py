from datetime import datetime
import os
import requests
import streamlit as st

from auth_view import (
    auth_headers,
    handle_unauthorized,
    logout_request,
    require_authentication,
)
from calendar_view import render_calendar

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Varhanici Log Page",
    page_icon="🎹",
    layout="wide",
)


def check_backend_health() -> bool:
    try:
        resp = requests.get(f"{API_BASE_URL}/health", headers=auth_headers(), timeout=2)
        handle_unauthorized(resp)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def fetch_logs() -> list[dict]:
    resp = requests.get(f"{API_BASE_URL}/api/logs", headers=auth_headers(), timeout=5)
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def create_log_entry(title: str, author: str, notes: str, entry_date: str | None = None) -> dict:
    payload = {"title": title, "author": author, "notes": notes or None, "date": entry_date}
    resp = requests.post(f"{API_BASE_URL}/api/logs", json=payload, headers=auth_headers(), timeout=5)
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def delete_log_entry(log_id: int) -> None:
    resp = requests.delete(f"{API_BASE_URL}/api/logs/{log_id}", headers=auth_headers(), timeout=5)
    handle_unauthorized(resp)
    resp.raise_for_status()


# --- Auth Gate ---
current_user = require_authentication(API_BASE_URL)

# --- Sidebar ---
with st.sidebar:
    st.title("🎹 Varhanici Log")
    user_label = f"👤 **{current_user.get('username', '')}**"
    if current_user.get("farnost"):
        user_label += f" ({current_user['farnost']})"
    st.markdown(user_label)
    if st.button("🚪 Odhlásit se", use_container_width=True):
        logout_request(API_BASE_URL)
        st.rerun()

    st.divider()
    is_healthy = check_backend_health()
    if is_healthy:
        st.success(f"Backend connected ({API_BASE_URL})")
    else:
        st.error(f"Backend unreachable ({API_BASE_URL})")
        st.caption("Start the FastAPI server with:\n`uvicorn backend.main:app --reload`")

    st.divider()
    st.subheader("New Log Entry")
    with st.form("create_log_form", clear_on_submit=True):
        title = st.text_input("Svátek", placeholder="např. 33.Neděle")
        author = st.text_input(
            "Varhaník",
            value=current_user.get("username", ""),
            placeholder="např. Jan Koňařík",
        )
        notes = st.text_area("Písně", placeholder="např. 519, 502, ...", height=100)
        col_date, col_time = st.columns(2)
        with col_date:
            entry_date = st.date_input("Datum", value=None, format="DD.MM.YYYY")
        with col_time:
            entry_time = st.time_input("Čas", value=None, step=300)
        submitted = st.form_submit_button("Přidat Záznam", use_container_width=True, disabled=not is_healthy)

        if submitted:
            if not title.strip() or not author.strip():
                st.warning("Please fill in both Title and Author.")
            else:
                try:
                    if entry_date and entry_time:
                        date_str = datetime.combine(entry_date, entry_time).strftime("%Y-%m-%dT%H:%M:%S")
                    elif entry_date:
                        date_str = entry_date.isoformat()
                    elif entry_time:
                        date_str = datetime.combine(datetime.now().date(), entry_time).strftime("%Y-%m-%dT%H:%M:%S")
                    else:
                        date_str = None
                    create_log_entry(title.strip(), author.strip(), notes.strip(), date_str)
                    st.toast("Log entry added!", icon="✅")
                    st.rerun()
                except requests.RequestException as exc:
                    st.error(f"Failed to create entry: {exc}")


# --- Main Content ---
st.header("Log Entries")

if not is_healthy:
    st.info("Waiting for the FastAPI backend to come online...")
else:
    try:
        logs = fetch_logs()
        tab_calendar, tab_list = st.tabs(["📅 Kalendář", "📋 Seznam záznamů"])

        with tab_calendar:
            render_calendar(logs)

        with tab_list:
            if not logs:
                st.info("No log entries yet. Use the sidebar form to create the first entry!")
            else:
                for entry in logs:
                    with st.container(border=True):
                        col_main, col_action = st.columns([5, 1])
                        with col_main:
                            st.subheader(entry["title"])
                            raw_ts = entry["created_at"]
                            try:
                                formatted_ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
                            except ValueError:
                                formatted_ts = raw_ts[:16].replace("T", " ")
                            st.caption(f"👤 **{entry['author']}** • 🕒 {formatted_ts}")
                            if entry.get("notes"):
                                st.write(entry["notes"])
                        with col_action:
                            if st.button("🗑️ Delete", key=f"del_{entry['id']}", use_container_width=True):
                                try:
                                    delete_log_entry(entry["id"])
                                    st.rerun()
                                except requests.RequestException as exc:
                                    st.error(f"Error deleting: {exc}")
    except requests.RequestException as exc:
        st.error(f"Error loading logs from backend: {exc}")
