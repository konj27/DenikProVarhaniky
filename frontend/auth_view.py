import requests
import streamlit as st


def _extract_error_detail(resp: requests.Response, fallback: str) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and isinstance(data.get("detail"), str):
            return data["detail"]
    except ValueError:
        pass
    return fallback


def auth_headers() -> dict[str, str]:
    token = st.session_state.get("auth_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def clear_auth_session() -> None:
    st.session_state.pop("auth_token", None)
    st.session_state.pop("current_user", None)
    st.session_state.pop("selected_parish_id", None)


def handle_unauthorized(resp: requests.Response) -> None:
    if resp.status_code == 401:
        clear_auth_session()
        st.session_state["auth_notice"] = (
            "Relace vypršela nebo byla odhlášena. Přihlaste se prosím znovu."
        )
        st.rerun()


def _fetch_available_parishes(api_base_url: str) -> list[dict]:
    resp = requests.get(f"{api_base_url}/api/parishes", timeout=5)
    resp.raise_for_status()
    return resp.json()


def _login_request(api_base_url: str, username: str, password: str) -> dict:
    resp = requests.post(
        f"{api_base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=5,
    )
    if not resp.ok:
        raise ValueError(_extract_error_detail(resp, "Přihlášení se nezdařilo."))
    return resp.json()


def _register_request(
    api_base_url: str,
    username: str,
    password: str,
    home_parish_id: int,
    master_password: str,
) -> dict:
    payload = {
        "username": username,
        "password": password,
        "home_parish_id": home_parish_id,
        "master_password": master_password,
    }
    resp = requests.post(
        f"{api_base_url}/api/auth/register",
        json=payload,
        timeout=5,
    )
    if not resp.ok:
        raise ValueError(_extract_error_detail(resp, "Registrace se nezdařila."))
    return resp.json()


def logout_request(api_base_url: str) -> None:
    try:
        requests.post(f"{api_base_url}/api/auth/logout", headers=auth_headers(), timeout=3)
    except requests.RequestException:
        pass
    finally:
        clear_auth_session()


def render_auth_gate(api_base_url: str) -> None:
    """Render login and registration view."""
    st.markdown(
        """
        <style>
        @media (max-width: 640px) {
            .block-container {
                padding-top: 2rem !important;
                padding-left: 0.75rem !important;
                padding-right: 0.75rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, col_center, _ = st.columns([1, 1.4, 1])
    with col_center:
        st.title("🎹 Deník varhaníka")
        st.caption("Pro přístup ke kalendáři a záznamům se prosím přihlaste.")

        notice = st.session_state.pop("auth_notice", None)
        if notice:
            st.warning(notice)

        tab_login, tab_register = st.tabs(["🔑 Přihlášení", "📝 Registrace"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Uživatelské jméno")
                password = st.text_input("Heslo", type="password")
                submit_login = st.form_submit_button("Přihlásit se", use_container_width=True)

                if submit_login:
                    if not username.strip() or not password:
                        st.warning("Vyplňte uživatelské jméno i heslo.")
                    else:
                        try:
                            data = _login_request(api_base_url, username.strip(), password)
                            st.session_state["auth_token"] = data["access_token"]
                            st.session_state["current_user"] = data["user"]
                            st.session_state.pop("selected_parish_id", None)
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                        except requests.RequestException:
                            st.error(
                                "Nelze se připojit k serveru. Zkontrolujte prosím, že aplikace běží."
                            )

        with tab_register:
            parishes: list[dict] = []
            parishes_error = False
            try:
                parishes = _fetch_available_parishes(api_base_url)
            except requests.RequestException:
                parishes_error = True

            if parishes_error:
                st.error("Nelze načíst seznam farností ze serveru.")

            with st.form("register_form"):
                reg_username = st.text_input("Uživatelské jméno", placeholder="min. 3 znaky")
                selected_parish = st.selectbox(
                    "Domovská farnost",
                    options=parishes,
                    format_func=lambda p: p["name"],
                    index=None,
                    placeholder="Vyberte svou domovskou farnost...",
                    disabled=not parishes,
                )
                reg_password = st.text_input("Heslo", type="password", placeholder="min. 6 znaků")
                reg_password_confirm = st.text_input("Potvrzení hesla", type="password")
                reg_master_password = st.text_input("Master heslo", type="password")
                submit_register = st.form_submit_button(
                    "Vytvořit účet",
                    use_container_width=True,
                    disabled=not parishes,
                )

                if submit_register:
                    if not reg_username.strip() or not reg_password or not reg_master_password:
                        st.warning("Vyplňte uživatelské jméno, heslo a master heslo.")
                    elif selected_parish is None:
                        st.warning("Vyberte prosím svou domovskou farnost.")
                    elif len(reg_username.strip()) < 3:
                        st.warning("Uživatelské jméno musí mít alespoň 3 znaky.")
                    elif len(reg_password) < 6:
                        st.warning("Heslo musí mít alespoň 6 znaků.")
                    elif reg_password != reg_password_confirm:
                        st.warning("Zadaná hesla se neshodují.")
                    else:
                        try:
                            data = _register_request(
                                api_base_url=api_base_url,
                                username=reg_username.strip(),
                                password=reg_password,
                                home_parish_id=selected_parish["id"],
                                master_password=reg_master_password,
                            )
                            st.session_state["auth_token"] = data["access_token"]
                            st.session_state["current_user"] = data["user"]
                            st.session_state["selected_parish_id"] = selected_parish["id"]
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                        except requests.RequestException:
                            st.error(
                                "Nelze se připojit k serveru. Zkontrolujte prosím, že aplikace běží."
                            )


def require_authentication(api_base_url: str) -> dict:
    """Stop rendering and display auth gate unless the user is authenticated."""
    if not st.session_state.get("auth_token"):
        render_auth_gate(api_base_url)
        st.stop()
    return st.session_state.get("current_user") or {}
