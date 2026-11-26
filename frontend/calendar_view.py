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
    """Render an interactive responsive HTML/CSS/JS calendar component."""
    events_json = _safe_json_for_script(logs)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
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
                -webkit-tap-highlight-color: transparent;
            }}
            body {{
                margin: 0;
                padding: 2px;
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
                gap: 8px;
                padding: 14px 18px;
                background: var(--panel);
                border-bottom: 1px solid var(--border);
            }}
            .month-title {{
                font-size: 1.2rem;
                font-weight: 700;
                margin: 0;
                white-space: nowrap;
            }}
            .nav-buttons {{
                display: flex;
                gap: 8px;
                flex-shrink: 0;
            }}
            .btn {{
                background: var(--bg);
                color: var(--text);
                border: 1px solid var(--border);
                border-radius: 8px;
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
            /* Mobile-only dot indicators and selected-day agenda panel */
            .mobile-dots {{
                display: none;
                align-items: center;
                justify-content: center;
                gap: 3px;
                margin-top: 2px;
                flex-wrap: wrap;
            }}
            .mobile-dot {{
                width: 6px;
                height: 6px;
                border-radius: 999px;
                background: var(--accent);
            }}
            .mobile-more {{
                font-size: 0.65rem;
                font-weight: 600;
                color: var(--accent);
            }}
            .mobile-agenda {{
                display: none;
                margin-top: 12px;
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                overflow: hidden;
            }}
            .mobile-agenda-header {{
                padding: 10px 14px;
                background: var(--panel);
                border-bottom: 1px solid var(--border);
                font-size: 0.9rem;
                font-weight: 700;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .mobile-agenda-count {{
                font-size: 0.78rem;
                font-weight: 500;
                color: var(--muted);
            }}
            .mobile-agenda-body {{
                padding: 10px 12px;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }}
            .agenda-empty {{
                color: var(--muted);
                font-size: 0.85rem;
                padding: 6px 2px;
            }}
            .agenda-card {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-left: 4px solid var(--accent);
                border-radius: 8px;
                padding: 10px 12px;
                cursor: pointer;
            }}
            .agenda-card-title {{
                font-size: 0.95rem;
                font-weight: 700;
                margin-bottom: 4px;
                overflow-wrap: anywhere;
            }}
            .agenda-card-meta {{
                font-size: 0.8rem;
                color: var(--muted);
                margin-bottom: 6px;
            }}
            .agenda-card-notes {{
                font-size: 0.85rem;
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                padding: 8px 10px;
                white-space: pre-wrap;
                overflow-wrap: anywhere;
            }}

            @media (max-width: 640px) {{
                .calendar-header {{
                    padding: 10px 12px;
                }}
                .month-title {{
                    font-size: 1rem;
                }}
                .nav-buttons {{
                    gap: 5px;
                }}
                .btn {{
                    padding: 6px 10px;
                    font-size: 0.82rem;
                    min-height: 34px;
                }}
                .btn-label {{
                    display: none;
                }}
                .weekdays {{
                    font-size: 0.72rem;
                    padding: 6px 0;
                }}
                .days-grid {{
                    grid-auto-rows: minmax(50px, auto);
                }}
                .day-cell {{
                    padding: 5px 2px;
                    align-items: center;
                    justify-content: flex-start;
                    cursor: pointer;
                }}
                .day-cell.selected {{
                    outline: 2px solid var(--accent);
                    outline-offset: -2px;
                    background: var(--accent-bg);
                }}
                .day-number {{
                    justify-content: center;
                    font-size: 0.82rem;
                    margin-bottom: 0;
                }}
                .day-cell.today .day-number span {{
                    padding: 1px 6px;
                }}
                .event-chip {{
                    display: none;
                }}
                .mobile-dots {{
                    display: flex;
                }}
                .mobile-agenda {{
                    display: block;
                }}
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
                padding: 12px;
            }}
            .modal-backdrop.active {{
                display: flex;
            }}
            .modal-card {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 10px;
                width: 100%;
                max-width: 420px;
                max-height: 85vh;
                overflow-y: auto;
                padding: 18px 20px;
                box-shadow: 0 12px 32px rgba(0,0,0,0.35);
            }}
            .modal-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 8px;
                margin-bottom: 12px;
            }}
            .modal-title {{
                margin: 0;
                font-size: 1.1rem;
                overflow-wrap: anywhere;
            }}
            .close-btn {{
                background: none;
                border: none;
                color: var(--muted);
                font-size: 1.25rem;
                cursor: pointer;
                padding: 2px 6px;
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
                overflow-wrap: anywhere;
                font-size: 0.85rem;
            }}
        </style>
    </head>
    <body>
        <div class="calendar-wrapper">
            <div class="calendar-header">
                <h2 class="month-title" id="monthTitle"></h2>
                <div class="nav-buttons">
                    <button class="btn" id="prevBtn" aria-label="Předchozí měsíc">◀<span class="btn-label"> Předchozí</span></button>
                    <button class="btn" id="todayBtn">Dnes</button>
                    <button class="btn" id="nextBtn" aria-label="Další měsíc"><span class="btn-label">Další </span>▶</button>
                </div>
            </div>
            <div class="weekdays">
                <div>Po</div><div>Út</div><div>St</div><div>Čt</div><div>Pá</div><div>So</div><div>Ne</div>
            </div>
            <div class="days-grid" id="daysGrid"></div>
        </div>

        <div class="mobile-agenda" id="mobileAgenda">
            <div class="mobile-agenda-header">
                <span id="agendaDateTitle"></span>
                <span class="mobile-agenda-count" id="agendaCount"></span>
            </div>
            <div class="mobile-agenda-body" id="agendaBody"></div>
        </div>

        <div class="modal-backdrop" id="modalBackdrop">
            <div class="modal-card">
                <div class="modal-header">
                    <h3 class="modal-title" id="modalTitle"></h3>
                    <button class="close-btn" id="closeModal" aria-label="Zavřít">✕</button>
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

            const nowInit = new Date();
            let currentYear = nowInit.getFullYear();
            let currentMonth = nowInit.getMonth();
            let selectedDateKey = formatLocalKey(currentYear, currentMonth, nowInit.getDate());

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

            function formatDisplayDate(dateKey) {{
                const parts = String(dateKey).split("-");
                return parts.length === 3 ? `${{parts[2]}}.${{parts[1]}}.${{parts[0]}}` : dateKey;
            }}

            function formatDisplayDateTime(dateKey, timeStr) {{
                const formattedDate = formatDisplayDate(dateKey);
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

            function groupEventsByDay() {{
                const eventsByDay = {{}};
                for (const ev of EVENTS) {{
                    const key = toDateKey(ev.date || ev.created_at);
                    if (!eventsByDay[key]) eventsByDay[key] = [];
                    eventsByDay[key].push(ev);
                }}
                return eventsByDay;
            }}

            function renderMobileAgenda(eventsByDay) {{
                const titleEl = document.getElementById("agendaDateTitle");
                const countEl = document.getElementById("agendaCount");
                const bodyEl = document.getElementById("agendaBody");

                const dayEvents = (eventsByDay[selectedDateKey] || []).slice().sort((a, b) => {{
                    const ta = toTimeStr(a.date || a.created_at);
                    const tb = toTimeStr(b.date || b.created_at);
                    return ta.localeCompare(tb);
                }});

                titleEl.textContent = "📅 " + formatDisplayDate(selectedDateKey);
                countEl.textContent = dayEvents.length === 1
                    ? "1 záznam"
                    : `${{dayEvents.length}} záznamů`;
                bodyEl.innerHTML = "";

                if (dayEvents.length === 0) {{
                    const empty = document.createElement("div");
                    empty.className = "agenda-empty";
                    empty.textContent = "Pro vybraný den zatím nejsou žádné záznamy. Klepněte na den s modrou tečkou.";
                    bodyEl.appendChild(empty);
                    return;
                }}

                for (const ev of dayEvents) {{
                    const card = document.createElement("div");
                    card.className = "agenda-card";

                    const timeStr = toTimeStr(ev.date || ev.created_at);
                    const titleDiv = document.createElement("div");
                    titleDiv.className = "agenda-card-title";
                    titleDiv.textContent = "🎹 " + ev.title;

                    const metaDiv = document.createElement("div");
                    metaDiv.className = "agenda-card-meta";
                    metaDiv.textContent = timeStr
                        ? `🕒 ${{timeStr}} • 👤 ${{ev.author}}`
                        : `👤 ${{ev.author}}`;

                    card.appendChild(titleDiv);
                    card.appendChild(metaDiv);

                    if (ev.notes) {{
                        const notesDiv = document.createElement("div");
                        notesDiv.className = "agenda-card-notes";
                        notesDiv.textContent = "🎶 " + ev.notes;
                        card.appendChild(notesDiv);
                    }}

                    card.addEventListener("click", () => openModal(ev, selectedDateKey));
                    bodyEl.appendChild(card);
                }}
            }}

            function renderCalendar() {{
                const grid = document.getElementById("daysGrid");
                grid.innerHTML = "";
                document.getElementById("monthTitle").textContent =
                    `${{MONTHS_CS[currentMonth]}} ${{currentYear}}`;

                const firstDayOfMonth = new Date(currentYear, currentMonth, 1);
                const startOffset = (firstDayOfMonth.getDay() + 6) % 7;
                const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
                const daysInPrevMonth = new Date(currentYear, currentMonth, 0).getDate();

                const today = new Date();
                const todayKey = formatLocalKey(today.getFullYear(), today.getMonth(), today.getDate());
                const eventsByDay = groupEventsByDay();

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
                    if (dateKey === selectedDateKey) {{
                        cell.classList.add("selected");
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

                    if (dayEvents.length > 0) {{
                        const dotsWrap = document.createElement("div");
                        dotsWrap.className = "mobile-dots";
                        const visibleDots = Math.min(dayEvents.length, 3);
                        for (let d = 0; d < visibleDots; d++) {{
                            const dot = document.createElement("span");
                            dot.className = "mobile-dot";
                            dotsWrap.appendChild(dot);
                        }}
                        if (dayEvents.length > 3) {{
                            const more = document.createElement("span");
                            more.className = "mobile-more";
                            more.textContent = `+${{dayEvents.length - 3}}`;
                            dotsWrap.appendChild(more);
                        }}
                        cell.appendChild(dotsWrap);
                    }}

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
                        chip.addEventListener("click", (e) => {{
                            e.stopPropagation();
                            openModal(ev, dateKey);
                        }});
                        cell.appendChild(chip);
                    }}

                    cell.addEventListener("click", () => {{
                        selectedDateKey = dateKey;
                        renderCalendar();
                    }});

                    grid.appendChild(cell);
                }}

                renderMobileAgenda(eventsByDay);
            }}

            document.getElementById("prevBtn").addEventListener("click", () => {{
                currentMonth--;
                if (currentMonth < 0) {{ currentMonth = 11; currentYear--; }}
                selectedDateKey = formatLocalKey(currentYear, currentMonth, 1);
                renderCalendar();
            }});
            document.getElementById("nextBtn").addEventListener("click", () => {{
                currentMonth++;
                if (currentMonth > 11) {{ currentMonth = 0; currentYear++; }}
                selectedDateKey = formatLocalKey(currentYear, currentMonth, 1);
                renderCalendar();
            }});
            document.getElementById("todayBtn").addEventListener("click", () => {{
                const now = new Date();
                currentYear = now.getFullYear();
                currentMonth = now.getMonth();
                selectedDateKey = formatLocalKey(currentYear, currentMonth, now.getDate());
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
