import json
import streamlit.components.v1 as components


def _safe_json_for_script(data: object) -> str:
    """Serialize data to JSON that cannot break out of an HTML <script> tag."""
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_calendar(logs: list[dict], height: int = 760) -> None:
    """Render an interactive HTML/CSS/JS calendar component using streamlit.components.v1.html."""
    events_json = _safe_json_for_script(logs)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8" />
        <style>
            :root {{
                --bg: #0e1117;
                --panel: #161b22;
                --panel-hover: #1f2733;
                --border: #30363d;
                --text: #e6edf3;
                --muted: #8b949e;
                --accent: #3b82f6;
                --accent-bg: rgba(59, 130, 246, 0.16);
                --chip-bg: #1e293b;
                --chip-border: #3b82f6;
            }}
            @media (prefers-color-scheme: light) {{
                :root {{
                    --bg: #ffffff;
                    --panel: #f8fafc;
                    --panel-hover: #f1f5f9;
                    --border: #e2e8f0;
                    --text: #0f172a;
                    --muted: #64748b;
                    --accent: #2563eb;
                    --accent-bg: rgba(37, 99, 235, 0.1);
                    --chip-bg: #eff6ff;
                    --chip-border: #3b82f6;
                }}
            }}
            * {{
                box-sizing: border-box;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            body {{
                margin: 0;
                padding: 4px;
                background: transparent;
                color: var(--text);
            }}
            .calendar-wrapper {{
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                overflow: hidden;
            }}
            .calendar-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 14px 18px;
                background: var(--panel);
                border-bottom: 1px solid var(--border);
            }}
            .month-title {{
                font-size: 1.2rem;
                font-weight: 700;
                margin: 0;
            }}
            .nav-buttons {{
                display: flex;
                gap: 8px;
            }}
            .btn {{
                background: var(--bg);
                color: var(--text);
                border: 1px solid var(--border);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 0.85rem;
                font-weight: 500;
                cursor: pointer;
                transition: background 0.15s, border-color 0.15s;
            }}
            .btn:hover {{
                background: var(--panel-hover);
                border-color: var(--accent);
            }}
            .weekdays {{
                display: grid;
                grid-template-columns: repeat(7, minmax(0, 1fr));
                background: var(--panel);
                border-bottom: 1px solid var(--border);
                text-align: center;
                font-size: 0.8rem;
                font-weight: 600;
                color: var(--muted);
                padding: 8px 0;
            }}
            .days-grid {{
                display: grid;
                grid-template-columns: repeat(7, minmax(0, 1fr));
                grid-auto-rows: minmax(105px, auto);
            }}
            .day-cell {{
                min-width: 0;
                overflow: hidden;
                border-right: 1px solid var(--border);
                border-bottom: 1px solid var(--border);
                padding: 6px;
                display: flex;
                flex-direction: column;
                gap: 4px;
                background: var(--bg);
                transition: background 0.12s;
            }}
            .day-cell:nth-child(7n) {{
                border-right: none;
            }}
            .day-cell.other-month {{
                opacity: 0.4;
                background: var(--panel);
            }}
            .day-cell.today {{
                background: var(--accent-bg);
            }}
            .day-number {{
                font-size: 0.8rem;
                font-weight: 600;
                color: var(--muted);
                margin-bottom: 2px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .day-cell.today .day-number span {{
                background: var(--accent);
                color: #fff;
                border-radius: 999px;
                padding: 2px 7px;
                font-size: 0.75rem;
            }}
            .event-chip {{
                max-width: 100%;
                min-width: 0;
                background: var(--chip-bg);
                border-left: 3px solid var(--chip-border);
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 0.75rem;
                cursor: pointer;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                transition: transform 0.1s, filter 0.1s;
            }}
            .event-chip:hover {{
                filter: brightness(1.12);
                transform: translateY(-1px);
            }}
            .event-chip .ev-title {{
                font-weight: 600;
                display: block;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .event-chip .ev-author {{
                display: block;
                font-size: 0.7rem;
                color: var(--muted);
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            /* Modal */
            .modal-backdrop {{
                display: none;
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.55);
                align-items: center;
                justify-content: center;
                z-index: 1000;
            }}
            .modal-backdrop.active {{
                display: flex;
            }}
            .modal-card {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 10px;
                width: 90%;
                max-width: 420px;
                padding: 18px 20px;
                box-shadow: 0 12px 32px rgba(0,0,0,0.35);
            }}
            .modal-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 12px;
            }}
            .modal-title {{
                margin: 0;
                font-size: 1.15rem;
                overflow-wrap: anywhere;
            }}
            .close-btn {{
                background: none;
                border: none;
                color: var(--muted);
                font-size: 1.2rem;
                cursor: pointer;
            }}
            .modal-row {{
                margin: 8px 0;
                font-size: 0.9rem;
            }}
            .modal-notes {{
                margin-top: 10px;
                padding: 10px;
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                white-space: pre-wrap;
                font-size: 0.85rem;
            }}
        </style>
    </head>
    <body>
        <div class="calendar-wrapper">
            <div class="calendar-header">
                <h2 class="month-title" id="monthTitle"></h2>
                <div class="nav-buttons">
                    <button class="btn" id="prevBtn">◀ Předchozí</button>
                    <button class="btn" id="todayBtn">Dnes</button>
                    <button class="btn" id="nextBtn">Další ▶</button>
                </div>
            </div>
            <div class="weekdays">
                <div>Po</div><div>Út</div><div>St</div><div>Čt</div><div>Pá</div><div>So</div><div>Ne</div>
            </div>
            <div class="days-grid" id="daysGrid"></div>
        </div>

        <div class="modal-backdrop" id="modalBackdrop">
            <div class="modal-card">
                <div class="modal-header">
                    <h3 class="modal-title" id="modalTitle"></h3>
                    <button class="close-btn" id="closeModal">✕</button>
                </div>
                <div class="modal-row" id="modalDate"></div>
                <div class="modal-row" id="modalAuthor"></div>
                <div class="modal-notes" id="modalNotes"></div>
            </div>
        </div>

        <script>
            const EVENTS = {events_json};
            const MONTHS_CS = [
                "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
                "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec"
            ];

            let currentDate = new Date();
            let currentYear = currentDate.getFullYear();
            let currentMonth = currentDate.getMonth();

            function toDateKey(dateStr) {{
                if (!dateStr) return "";
                return String(dateStr).slice(0, 10);
            }}

            function toTimeStr(dateStr) {{
                if (!dateStr) return "";
                const str = String(dateStr);
                if (str.length >= 16 && (str[10] === "T" || str[10] === " ")) {{
                    return str.slice(11, 16);
                }}
                return "";
            }}

            function formatDisplayDateTime(dateKey, timeStr) {{
                const parts = String(dateKey).split("-");
                const formattedDate = parts.length === 3 ? `${{parts[2]}}.${{parts[1]}}.${{parts[0]}}` : dateKey;
                return timeStr ? `${{formattedDate}} ${{timeStr}}` : formattedDate;
            }}

            function formatLocalKey(year, month, day) {{
                const m = String(month + 1).padStart(2, "0");
                const d = String(day).padStart(2, "0");
                return `${{year}}-${{m}}-${{d}}`;
            }}

            function openModal(ev, dateKey) {{
                const timeStr = toTimeStr(ev.date || ev.created_at);
                document.getElementById("modalTitle").textContent = "🎹 " + ev.title;
                document.getElementById("modalDate").textContent = "📅 Datum a čas: " + formatDisplayDateTime(dateKey, timeStr);
                document.getElementById("modalAuthor").textContent = "👤 Varhaník: " + ev.author;
                const notesEl = document.getElementById("modalNotes");
                if (ev.notes) {{
                    notesEl.style.display = "block";
                    notesEl.textContent = "🎶 Písně:\\n" + ev.notes;
                }} else {{
                    notesEl.style.display = "none";
                }}
                document.getElementById("modalBackdrop").classList.add("active");
            }}

            function renderCalendar() {{
                const grid = document.getElementById("daysGrid");
                grid.innerHTML = "";
                document.getElementById("monthTitle").textContent =
                    `${{MONTHS_CS[currentMonth]}} ${{currentYear}}`;

                const firstDayOfMonth = new Date(currentYear, currentMonth, 1);
                // Convert Sunday=0..Saturday=6 into Monday=0..Sunday=6
                const startOffset = (firstDayOfMonth.getDay() + 6) % 7;
                const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
                const daysInPrevMonth = new Date(currentYear, currentMonth, 0).getDate();

                const today = new Date();
                const todayKey = formatLocalKey(today.getFullYear(), today.getMonth(), today.getDate());

                // Group events by YYYY-MM-DD
                const eventsByDay = {{}};
                for (const ev of EVENTS) {{
                    const key = toDateKey(ev.date || ev.created_at);
                    if (!eventsByDay[key]) eventsByDay[key] = [];
                    eventsByDay[key].push(ev);
                }}

                const totalCells = Math.ceil((startOffset + daysInMonth) / 7) * 7;

                for (let i = 0; i < totalCells; i++) {{
                    const cell = document.createElement("div");
                    cell.className = "day-cell";

                    let cellYear = currentYear;
                    let cellMonth = currentMonth;
                    let dayNum = 0;

                    if (i < startOffset) {{
                        dayNum = daysInPrevMonth - startOffset + 1 + i;
                        cellMonth = currentMonth - 1;
                        if (cellMonth < 0) {{ cellMonth = 11; cellYear--; }}
                        cell.classList.add("other-month");
                    }} else if (i >= startOffset + daysInMonth) {{
                        dayNum = i - (startOffset + daysInMonth) + 1;
                        cellMonth = currentMonth + 1;
                        if (cellMonth > 11) {{ cellMonth = 0; cellYear++; }}
                        cell.classList.add("other-month");
                    }} else {{
                        dayNum = i - startOffset + 1;
                    }}

                    const dateKey = formatLocalKey(cellYear, cellMonth, dayNum);
                    if (dateKey === todayKey) {{
                        cell.classList.add("today");
                    }}

                    const numDiv = document.createElement("div");
                    numDiv.className = "day-number";
                    numDiv.innerHTML = `<span>${{dayNum}}.</span>`;
                    cell.appendChild(numDiv);

                    const dayEvents = (eventsByDay[dateKey] || []).slice().sort((a, b) => {{
                        const ta = toTimeStr(a.date || a.created_at);
                        const tb = toTimeStr(b.date || b.created_at);
                        return ta.localeCompare(tb);
                    }});
                    for (const ev of dayEvents) {{
                        const chip = document.createElement("div");
                        chip.className = "event-chip";
                        chip.title = ev.title || "";
                        const timeStr = toTimeStr(ev.date || ev.created_at);
                        const rawTitle = String(ev.title || "");
                        const shortTitle = rawTitle.length > 20 ? rawTitle.slice(0, 20) + "..." : rawTitle;

                        const titleSpan = document.createElement("span");
                        titleSpan.className = "ev-title";
                        titleSpan.textContent = timeStr ? `🕒 ${{timeStr}} 🎹 ${{shortTitle}}` : `🎹 ${{shortTitle}}`;

                        const authorSpan = document.createElement("span");
                        authorSpan.className = "ev-author";
                        authorSpan.textContent = ev.author;

                        chip.appendChild(titleSpan);
                        chip.appendChild(authorSpan);
                        chip.addEventListener("click", () => openModal(ev, dateKey));
                        cell.appendChild(chip);
                    }}

                    grid.appendChild(cell);
                }}
            }}

            document.getElementById("prevBtn").addEventListener("click", () => {{
                currentMonth--;
                if (currentMonth < 0) {{ currentMonth = 11; currentYear--; }}
                renderCalendar();
            }});
            document.getElementById("nextBtn").addEventListener("click", () => {{
                currentMonth++;
                if (currentMonth > 11) {{ currentMonth = 0; currentYear++; }}
                renderCalendar();
            }});
            document.getElementById("todayBtn").addEventListener("click", () => {{
                const now = new Date();
                currentYear = now.getFullYear();
                currentMonth = now.getMonth();
                renderCalendar();
            }});
            document.getElementById("closeModal").addEventListener("click", () => {{
                document.getElementById("modalBackdrop").classList.remove("active");
            }});
            document.getElementById("modalBackdrop").addEventListener("click", (e) => {{
                if (e.target.id === "modalBackdrop") {{
                    document.getElementById("modalBackdrop").classList.remove("active");
                }}
            }});

            renderCalendar();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height, scrolling=True)
