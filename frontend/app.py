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
    page_title="Varhanici Deník",
    page_icon="🎹",
    layout="wide",
)


def _extract_error(resp: requests.Response, fallback: str) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and isinstance(data.get("detail"), str):
            return data["detail"]
    except ValueError:
        pass
    return fallback


def _format_timestamp(raw_ts: str) -> str:
    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return raw_ts[:16].replace("T", " ")


def fetch_my_parishes() -> list[dict]:
    resp = requests.get(f"{API_BASE_URL}/api/parishes/mine", headers=auth_headers(), timeout=5)
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def fetch_all_parishes() -> list[dict]:
    resp = requests.get(f"{API_BASE_URL}/api/parishes", timeout=5)
    resp.raise_for_status()
    return resp.json()


def fetch_my_access_requests() -> list[dict]:
    resp = requests.get(
        f"{API_BASE_URL}/api/access-requests/mine",
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def submit_access_request(parish_id: int) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/api/access-requests",
        json={"parish_id": parish_id},
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    if not resp.ok:
        raise ValueError(_extract_error(resp, "Žádost se nepodařilo odeslat."))
    return resp.json()


def fetch_admin_access_requests() -> list[dict]:
    resp = requests.get(
        f"{API_BASE_URL}/api/admin/access-requests",
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def delete_access_request(request_id: int) -> dict:
    resp = requests.delete(
        f"{API_BASE_URL}/api/admin/access-requests/{request_id}",
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def grant_user_parish(user_id: int, parish_id: int) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/api/admin/user-parishes",
        json={"user_id": user_id, "parish_id": parish_id},
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def create_denied_request(
    user_id: int,
    parish_id: int,
    requested_at: str | None = None,
    reason: str | None = None,
) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/api/admin/denied-requests",
        json={
            "user_id": user_id,
            "parish_id": parish_id,
            "requested_at": requested_at,
            "reason": reason,
        },
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def fetch_logs(parish_id: int) -> list[dict]:
    resp = requests.get(
        f"{API_BASE_URL}/api/logs",
        params={"parish_id": parish_id},
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    resp.raise_for_status()
    return resp.json()


def create_log_entry(
    title: str,
    author: str,
    notes: str,
    parish_id: int,
    entry_date: str | None = None,
) -> dict:
    payload = {
        "title": title,
        "author": author,
        "notes": notes or None,
        "date": entry_date,
        "parish_id": parish_id,
    }
    resp = requests.post(
        f"{API_BASE_URL}/api/logs",
        json=payload,
        headers=auth_headers(),
        timeout=5,
    )
    handle_unauthorized(resp)
    if not resp.ok:
        raise ValueError(_extract_error(resp, "Nepodařilo se vytvořit záznam."))
    return resp.json()


def delete_log_entry(log_id: int) -> None:
    resp = requests.delete(f"{API_BASE_URL}/api/logs/{log_id}", headers=auth_headers(), timeout=5)
    handle_unauthorized(resp)
    if not resp.ok:
        raise ValueError(_extract_error(resp, "Záznam se nepodařilo smazat."))


# --- Auth Gate ---
current_user = require_authentication(API_BASE_URL)
is_admin = bool(current_user.get("is_admin", False))

# --- Load Parishes ---
backend_available = True
my_parishes: list[dict] = []
all_parishes: list[dict] = []
my_pending_requests: list[dict] = []

try:
    my_parishes = fetch_my_parishes()
    if not is_admin:
        all_parishes = fetch_all_parishes()
        my_pending_requests = fetch_my_access_requests()
except requests.RequestException:
    backend_available = False

selected_parish: dict | None = None

# --- Sidebar ---
with st.sidebar:
    st.title("🎹 Deník varhaníka")
    user_label = f"👤 **{current_user.get('username', '')}**"
    if is_admin:
        user_label += " • 🛡️ Admin"
    elif current_user.get("farnost"):
        user_label += f" ({current_user['farnost']})"
    st.markdown(user_label)
    if st.button("🚪 Odhlásit se", use_container_width=True):
        logout_request(API_BASE_URL)
        st.rerun()

    st.divider()
    st.subheader("⛪ Farnost")
    if not backend_available:
        st.error("Nepodařilo se připojit k serveru.")
    elif not my_parishes:
        st.warning("Nemáte přiřazenou žádnou farnost.")
    else:
        parish_ids = [p["id"] for p in my_parishes]
        current_selected_id = st.session_state.get("selected_parish_id")
        if current_selected_id not in parish_ids:
            current_selected_id = parish_ids[0]
            st.session_state["selected_parish_id"] = current_selected_id

        default_index = parish_ids.index(current_selected_id)
        selected_parish = st.selectbox(
            "Přepnout farnost",
            options=my_parishes,
            index=default_index,
            format_func=lambda p: f"🏠 {p['name']}" if p.get("is_home") else p["name"],
            label_visibility="collapsed",
        )
        if selected_parish is not None:
            st.session_state["selected_parish_id"] = selected_parish["id"]

        if not is_admin:
            pending_parish_ids = {req["parish_id"] for req in my_pending_requests}
            if my_pending_requests:
                pending_names = ", ".join(req["parish_name"] for req in my_pending_requests)
                st.caption(f"⏳ Čeká na schválení: {pending_names}")

            requestable_parishes = [
                p
                for p in all_parishes
                if p["id"] not in parish_ids and p["id"] not in pending_parish_ids
            ]
            if requestable_parishes:
                with st.expander("➕ Požádat o další farnost"):
                    requested_parish = st.selectbox(
                        "Vyberte farnost",
                        options=requestable_parishes,
                        format_func=lambda p: p["name"],
                        key="request_parish_select",
                    )
                    if st.button("Odeslat žádost", use_container_width=True, key="send_req_btn"):
                        try:
                            submit_access_request(requested_parish["id"])
                            st.toast(
                                f"Žádost pro farnost {requested_parish['name']} byla odeslána.",
                                icon="📩",
                            )
                            st.rerun()
                        except ValueError as exc:
                            st.warning(str(exc))
                        except requests.RequestException as exc:
                            st.error(f"Nepodařilo se odeslat žádost: {exc}")

    st.divider()
    st.subheader("Nový záznam")
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
        submitted = st.form_submit_button(
            "Přidat Záznam",
            use_container_width=True,
            disabled=not backend_available or selected_parish is None,
        )

        if submitted:
            if not title.strip() or not author.strip():
                st.warning("Vyplňte prosím Svátek i Varhaníka.")
            elif selected_parish is None:
                st.warning("Nejprve vyberte farnost.")
            else:
                try:
                    if entry_date and entry_time:
                        date_str = datetime.combine(entry_date, entry_time).strftime(
                            "%Y-%m-%dT%H:%M:%S"
                        )
                    elif entry_date:
                        date_str = entry_date.isoformat()
                    elif entry_time:
                        date_str = datetime.combine(datetime.now().date(), entry_time).strftime(
                            "%Y-%m-%dT%H:%M:%S"
                        )
                    else:
                        date_str = None
                    create_log_entry(
                        title=title.strip(),
                        author=author.strip(),
                        notes=notes.strip(),
                        parish_id=selected_parish["id"],
                        entry_date=date_str,
                    )
                    st.toast("Záznam byl přidán!", icon="✅")
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))
                except requests.RequestException as exc:
                    st.error(f"Nepodařilo se vytvořit záznam: {exc}")


# --- Custom Styling for Admin Approve / Deny Buttons ---
if is_admin:
    st.markdown(
        """
        <style>
        div[class*="st-key-approve_req_"] button {
            background-color: #16a34a !important;
            border-color: #15803d !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 1.05rem !important;
        }
        div[class*="st-key-approve_req_"] button:hover {
            background-color: #15803d !important;
            border-color: #166534 !important;
            color: #ffffff !important;
        }
        div[class*="st-key-deny_req_"] button {
            background-color: #dc2626 !important;
            border-color: #b91c1c !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 1.05rem !important;
        }
        div[class*="st-key-deny_req_"] button:hover {
            background-color: #b91c1c !important;
            border-color: #991b1b !important;
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _can_delete_log(entry: dict) -> bool:
    if is_admin:
        return True
    owner_id = entry.get("created_by_user_id")
    if owner_id is not None:
        return owner_id == current_user.get("id")
    return (entry.get("author") or "").strip() == current_user.get("username")


def _render_logs_list(logs: list[dict]) -> None:
    if not logs:
        st.info("V této farnosti zatím nejsou žádné záznamy. Přidejte první v levém panelu!")
        return

    for entry in logs:
        with st.container(border=True):
            col_main, col_action = st.columns([5, 1])
            with col_main:
                st.subheader(entry["title"])
                formatted_ts = _format_timestamp(entry["created_at"])
                st.caption(f"👤 **{entry['author']}** • 🕒 {formatted_ts}")
                if entry.get("notes"):
                    st.write(entry["notes"])
            with col_action:
                if _can_delete_log(entry):
                    if st.button("🗑️ Smazat", key=f"del_{entry['id']}", use_container_width=True):
                        try:
                            delete_log_entry(entry["id"])
                            st.rerun()
                        except ValueError as exc:
                            st.warning(str(exc))
                        except requests.RequestException as exc:
                            st.error(f"Chyba při mazání: {exc}")


def _render_admin_requests_tab(requests_list: list[dict]) -> None:
    st.subheader("Nevyřízené žádosti o přístup do farností")
    if not requests_list:
        st.info("Momentálně nejsou žádné nevyřízené žádosti.")
        return

    for req in requests_list:
        with st.container(border=True):
            col_info, col_allow, col_deny = st.columns([8, 1, 1], vertical_alignment="center")
            with col_info:
                formatted_ts = _format_timestamp(req["created_at"])
                st.markdown(
                    f"👤 **{req['username']}** žádá o přístup do farnosti ⛪ **{req['parish_name']}**"
                )
                st.caption(f"🕒 Odesláno: {formatted_ts}")
            with col_allow:
                if st.button(
                    "✓",
                    key=f"approve_req_{req['id']}",
                    help="Povolit přístup",
                    use_container_width=True,
                ):
                    try:
                        deleted = delete_access_request(req["id"])
                        grant_user_parish(deleted["user_id"], deleted["parish_id"])
                        st.toast(
                            f"Přístup pro {deleted['username']} ({deleted['parish_name']}) povolen.",
                            icon="✅",
                        )
                        st.rerun()
                    except requests.RequestException as exc:
                        st.error(f"Nepodařilo se povolit žádost: {exc}")
            with col_deny:
                if st.button(
                    "✕",
                    key=f"deny_req_{req['id']}",
                    help="Zamítnout přístup",
                    use_container_width=True,
                ):
                    try:
                        deleted = delete_access_request(req["id"])
                        create_denied_request(
                            user_id=deleted["user_id"],
                            parish_id=deleted["parish_id"],
                            requested_at=deleted["created_at"],
                        )
                        st.toast(
                            f"Žádost uživatele {deleted['username']} byla zamítnuta.",
                            icon="❌",
                        )
                        st.rerun()
                    except requests.RequestException as exc:
                        st.error(f"Nepodařilo se zamítnout žádost: {exc}")


# --- Main Content ---
if not backend_available:
    st.header("Varhanici Log")
    st.info("Čekání na připojení k serveru...")
elif selected_parish is None:
    st.header("Varhanici Log")
    st.info("Není vybrána žádná farnost.")
else:
    st.header(f"Záznamy — {selected_parish['name']}")
    try:
        logs = fetch_logs(selected_parish["id"])
        if is_admin:
            pending_admin_requests = fetch_admin_access_requests()
            req_count = len(pending_admin_requests)
            admin_tab_label = (
                f"🛡️ Žádosti o přístup ({req_count})" if req_count > 0 else "🛡️ Žádosti o přístup"
            )
            tab_calendar, tab_list, tab_requests = st.tabs(
                ["📅 Kalendář", "📋 Seznam záznamů", admin_tab_label]
            )
            with tab_calendar:
                render_calendar(logs)
            with tab_list:
                _render_logs_list(logs)
            with tab_requests:
                _render_admin_requests_tab(pending_admin_requests)
        else:
            tab_calendar, tab_list = st.tabs(["📅 Kalendář", "📋 Seznam záznamů"])
            with tab_calendar:
                render_calendar(logs)
            with tab_list:
                _render_logs_list(logs)
    except requests.RequestException as exc:
        st.error(f"Nepodařilo se načíst záznamy: {exc}")
