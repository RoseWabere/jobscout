"""
automated job hunting system- streamlit
Run:  streamlit run app.py
"""
import sys, time, json
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import database as db
from modules import scrapers, analyzer, cv_parser, generator, notifier, excel_export

# ==========================================================================
# --- Ensure Playwright browsers are installed for Streamlit Cloud ---
import subprocess

@st.cache_resource
def _install_playwright():
    try:
        subprocess.run(
            ["playwright", "install", "chromium"],
            check=True
        )
    except Exception:
        pass  # avoid crashing app if already installed

_install_playwright()

# ==========================================================================
#  PAGE CONFIG

st.set_page_config(
    page_title="JobScout KE",
    page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%232A9D8F'/><text y='.9em' x='18' font-size='60'>JS</text></svg>",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================================
#  DESIGN SYSTEM

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {
  /* canvas */
  --bg:       #0E0D09;
  --surface:  #161410;
  --card:     #1C1A14;
  --card2:    #211F18;
  --border:   #2C291F;
  --border2:  #36331F;

  /* text */
  --text:     #E8E0D0;
  --text2:    #A89E8C;
  --muted:    #68604E;

  /* accents */
  --teal:     #2A9D8F;
  --teal2:    #1A6058;
  --amber:    #C8872A;
  --amber2:   #7A5010;
  --green:    #4D9663;
  --red:      #A84848;
  --yellow:   #B89830;

  /* type */
  --serif:   'Fraunces', Georgia, serif;
  --sans:    'DM Sans', system-ui, sans-serif;
  --mono:    'DM Mono', 'Fira Mono', monospace;
}

/* ── Reset ── */
html, body, [class*="css"] { font-family: var(--sans) !important; }
.stApp { background: var(--bg); color: var(--text); }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}

/* ── Topbar ── */
.topbar {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 1.1rem 0 1.2rem;
  margin: -1rem 0 1.4rem;
}
.topbar-name {
  font-family: var(--serif);
  font-size: 1.55rem;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -.03em;
  line-height: 1;
}
.topbar-sub {
  font-size: .7rem;
  color: var(--muted);
  letter-spacing: .07em;
  text-transform: uppercase;
  margin-top: 5px;
}
.live-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--green);
  display: inline-block;
  margin-right: 6px;
  vertical-align: middle;
  animation: breathe 2.4s ease-in-out infinite;
}
@keyframes breathe {
  0%,100% { opacity:1; } 50% { opacity:.3; }
}

/* ── Section label ── */
.slabel {
  font-size: .62rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: .12em;
  border-bottom: 1px solid var(--border);
  padding-bottom: 5px;
  margin: 1.1rem 0 .7rem;
}

/* ── Stat cards ── */
.scard {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 13px 15px;
  text-align: center;
  transition: border-color .2s;
}
.scard:hover { border-color: var(--border2); }
.sn {
  font-family: var(--mono);
  font-size: 1.65rem;
  font-weight: 500;
  line-height: 1;
}
.sl {
  font-size: .65rem; color: var(--muted);
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: .07em;
}

/* ── Job cards ── */
.jcard {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 14px 16px;
  margin: 7px 0;
  position: relative;
  transition: border-color .15s, transform .1s;
}
.jcard:hover { border-color: var(--border2); transform: translateY(-1px); }
.jcard.new     { border-left: 3px solid var(--teal); }
.jcard.pend    { border-left: 3px solid var(--amber); }
.jcard.applied { border-left: 3px solid var(--green); opacity: .88; }
.jcard.skipped { border-left: 3px solid var(--muted); opacity: .42; }

.jtitle   { font-size: .93rem; font-weight: 600; color: var(--text); margin: 0 0 3px; }
.jcompany { font-size: .78rem; color: var(--teal); margin: 0 0 5px; }
.jmeta    { font-size: .7rem; color: var(--muted);
            display: flex; gap: .75rem; flex-wrap: wrap; align-items: center; }

.badge {
  display: inline-block;
  background: var(--card2);
  border: 1px solid var(--border);
  color: var(--text2);
  font-size: .6rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: .05em;
}

.pill {
  display: inline-block;
  font-size: .6rem; font-weight: 600;
  padding: 1px 7px; border-radius: 20px;
  text-transform: uppercase; letter-spacing: .05em;
}
.pill.new     { background:rgba(42,157,143,.1); color:var(--teal); }
.pill.pend    { background:rgba(200,135,42,.1);  color:var(--amber); }
.pill.applied { background:rgba(77,150,99,.1);   color:var(--green); }
.pill.skipped { background:rgba(104,96,78,.08);  color:var(--muted); }

/* ── Score chip ── */
.sc {
  position: absolute; top: 13px; right: 14px;
  font-family: var(--mono);
  font-size: .78rem; font-weight: 500;
  padding: 2px 8px; border-radius: 5px;
}
.sc.hi  { background:rgba(77,150,99,.13);  color:var(--green); }
.sc.mid { background:rgba(184,152,48,.12); color:var(--yellow); }
.sc.lo  { background:rgba(104,96,78,.1);   color:var(--muted); }

/* ── Keyword chips ── */
.kw { display:inline-block; font-family:var(--mono); font-size:.68rem;
      background:var(--card2); border:1px solid var(--border);
      color:var(--text2); padding:2px 7px; border-radius:4px; margin:2px; }
.kw.m { background:rgba(42,157,143,.08); border-color:var(--teal2); color:var(--teal); }
.kw.x { background:rgba(168,72,72,.08);  border-color:#6B2A2A; color:var(--red); }

/* ── Note boxes ── */
.note {
  border-radius: 8px; padding: 10px 14px;
  font-size: .8rem; line-height: 1.55; margin: 7px 0;
}
.note.info { background:rgba(42,157,143,.06); border:1px solid rgba(42,157,143,.18); color:#7EC8C0; }
.note.warn { background:rgba(200,135,42,.06); border:1px solid rgba(200,135,42,.18); color:#C8A060; }
.note.good { background:rgba(77,150,99,.06);  border:1px solid rgba(77,150,99,.18);  color:#80B890; }
.note.err  { background:rgba(168,72,72,.06);  border:1px solid rgba(168,72,72,.18);  color:#C88080; }

/* ── Log terminal ── */
.log {
  background: #070604;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  font-family: var(--mono);
  font-size: .7rem;
  color: #6AB87A;
  max-height: 210px;
  overflow-y: auto;
  line-height: 1.75;
  white-space: pre-wrap;
}

/* ── CV preview ── */
.cvbox {
  background: #070604;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  font-family: var(--mono);
  font-size: .73rem;
  color: var(--text2);
  max-height: 260px;
  overflow-y: auto;
  line-height: 1.7;
  white-space: pre-wrap;
}

/* ── Score bar ── */
.bar-wrap { width:100%; background:var(--border); border-radius:3px; height:4px; }
.bar-fill { height:4px; border-radius:3px; background:var(--amber); transition:width .4s; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: var(--surface); border-radius:8px 8px 0 0; gap:0;
  border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
  background: transparent; color: var(--muted);
  border-bottom: 2px solid transparent;
  padding: 8px 17px; font-size: .8rem; font-weight: 500;
}
.stTabs [aria-selected="true"] {
  color: var(--text) !important;
  border-bottom: 2px solid var(--amber) !important;
  background: transparent !important;
}

/* ── Inputs ── */
.stTextInput > div > div,
.stTextArea textarea,
.stSelectbox > div > div {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 7px !important;
  color: var(--text) !important;
  font-family: var(--sans) !important;
}
.stTextInput > div > div:focus-within,
.stTextArea textarea:focus {
  border-color: var(--amber2) !important;
}

/* ── Buttons ── */
.stButton > button {
  background: var(--card); color: var(--text2);
  border: 1px solid var(--border); border-radius: 7px;
  font-family: var(--sans); font-size: .78rem; font-weight: 500;
  transition: all .14s; padding: .38rem .95rem;
}
.stButton > button:hover {
  background: var(--card2); border-color: var(--border2); color: var(--text);
}
.stButton > button[kind="primary"] {
  background: var(--amber); color: #0E0D09;
  border-color: var(--amber); font-weight: 600;
}
.stButton > button[kind="primary"]:hover {
  background: #D9952E; border-color: #D9952E;
}

/* ── Progress ── */
.stProgress > div > div { background: var(--amber); border-radius: 4px; }

/* ── Expander ── */
.streamlit-expanderHeader {
  background: var(--card) !important; color: var(--text2) !important;
  border-radius: 7px !important; font-size: .8rem !important;
  border: 1px solid var(--border) !important;
}
hr { border-color: var(--border) !important; margin: .7rem 0 !important; }
.stSlider > div > div > div { background: var(--amber) !important; }

/* ── Serif heading ── */
.sh {
  font-family: var(--serif);
  font-size: 1.1rem; font-weight: 300; font-style: italic;
  color: var(--text2); margin-bottom: .25rem;
}
</style>
""", unsafe_allow_html=True)


# ==========================================================================
#  SESSION STATE

def _init():
    defaults = {"cv": None, "cv_path": None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
_init()


# ==========================================================================
#  SIDEBAR

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding:.9rem 1rem 1.1rem">
          <div style="font-family:var(--serif);font-size:1.35rem;
                      font-weight:600;color:var(--text);letter-spacing:-.02em">
            JobScout KE
          </div>
          <div style="font-size:.65rem;color:var(--muted);
                      letter-spacing:.08em;text-transform:uppercase;margin-top:3px">
            Rose Wabere
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Service health
        st.markdown('<div class="slabel">Services</div>', unsafe_allow_html=True)
        h = config.health()
        labels = [("groq","Groq LLM"),("telegram","Telegram"),
                  ("whatsapp","WhatsApp bot"),("postgres","PostgreSQL"),
                  ("smtp","Email SMTP")]
        for key, lbl in labels:
            ok  = h.get(key, False)
            col = "var(--green)" if ok else "var(--muted)"
            dot = "&#9679;" if ok else "&#9675;"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:3px 0;font-size:.76rem;color:var(--text2)">'
                f'<span>{lbl}</span>'
                f'<span style="color:{col}">{dot}</span></div>',
                unsafe_allow_html=True,
            )

        # CV Upload
        st.markdown('<div class="slabel">Your CV</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Upload PDF resume", type=["pdf"], label_visibility="collapsed"
        )
        if uploaded:
            cv_path = config.UPLOADS_DIR / uploaded.name
            cv_path.write_bytes(uploaded.getbuffer())
            with st.spinner("Parsing CV..."):
                parsed = cv_parser.parse_cv(cv_path)
            if "error" in parsed:
                st.error(parsed["error"])
            else:
                st.session_state.cv      = parsed
                st.session_state.cv_path = cv_path
                db.save_cv(
                    parsed["file_name"], parsed["raw_text"],
                    parsed["skills"], parsed["contact"], parsed["sections"],
                )
                st.success(f"Parsed — {parsed['word_count']} words, "
                           f"{parsed['num_pages']} page(s)")
                if parsed["skills"]:
                    st.caption(", ".join(parsed["skills"][:7]) + "...")

        # Load saved CV if none in session
        if not st.session_state.cv:
            cv_row = db.get_latest_cv()
            if cv_row:
                st.session_state.cv = {
                    "raw_text": cv_row["raw_text"],
                    "skills":   cv_row["skills"],
                    "contact":  cv_row["contact"],
                    "sections": cv_row["sections"],
                    "file_name": cv_row["filename"],
                }
                st.caption(f"Using saved: {cv_row['filename']}")

        # Quick actions
        st.markdown('<div class="slabel">Quick Actions</div>', unsafe_allow_html=True)

        if st.button("Check Telegram callbacks", use_container_width=True):
            _process_callbacks()

        if st.button("Send test notification", use_container_width=True):
            ok = notifier.send_test("JobScout KE is running fine.")
            st.success("Telegram message sent") if ok else st.error(
                "Telegram not configured — add token + chat_id in Settings tab"
            )

        if st.button("Export to Excel", use_container_width=True):
            try:
                path = excel_export.export_to_excel(db.get_jobs())
                with open(path, "rb") as f:
                    st.download_button(
                        "Download Excel file", f,
                        file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            except Exception as e:
                st.error(f"Excel export error: {e}")


# ==========================================================================
#  TOPBAR

def render_topbar():
    stats = db.get_stats()
    st.markdown(f"""
    <div class="topbar">
      <div class="topbar-name">JobScout KE</div>
      <div class="topbar-sub">
        <span class="live-dot"></span>
        Active &nbsp;&#8212;&nbsp;
        {stats['today']} scraped today &nbsp;&#183;&nbsp;
        {stats['new']} new &nbsp;&#183;&nbsp;
        {stats['pending']} awaiting review &nbsp;&#183;&nbsp;
        {stats['applied']} applied
      </div>
    </div>
    """, unsafe_allow_html=True)


# ==========================================================================
#  TAB 1 — DASHBOARD

def tab_dashboard():
    stats = db.get_stats()

    c1,c2,c3,c4,c5 = st.columns(5)
    _stat(c1, stats["total"],   "Total tracked",   "var(--text2)")
    _stat(c2, stats["today"],   "Scraped today",   "var(--teal)")
    _stat(c3, stats["new"],     "New / unread",    "var(--amber)")
    _stat(c4, stats["pending"], "Pending review",  "var(--yellow)")
    _stat(c5, stats["applied"], "Applied",         "var(--green)")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns([1.4, 1])

    with col_l:
        st.markdown('<div class="slabel">Run a scrape</div>', unsafe_allow_html=True)
        s = db.load_settings()
        kw_raw   = s.get("user_keywords", "")
        kw_list  = [k.strip() for k in kw_raw.split(",") if k.strip()] or None
        max_days = int(s.get("max_days", "7"))

        sources = st.multiselect(
            "Sources",
            list(scrapers.SOURCE_MAP.keys()),
            default=["BrighterMonday","Fuzu","MyJobMag","MyJobsInKenya"],
            label_visibility="collapsed",
        )
        if st.button("Start scraping", type="primary", use_container_width=True):
            _run_scrape(sources, kw_list, max_days)

        st.markdown('<div class="slabel">Source history</div>', unsafe_allow_html=True)
        logs = db.get_scrape_log(limit=16)
        if logs:
            for row in logs[:10]:
                ok  = row["status"] == "ok"
                dot = "&#9679;"
                col = "var(--green)" if ok else "var(--red)"
                ts  = row["timestamp"][:16]
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:4px 0;border-bottom:1px solid var(--border);font-size:.76rem">'
                    f'<span><span style="color:{col}">{dot}</span> '
                    f'<span style="color:var(--text2)">{row["source"]}</span></span>'
                    f'<span style="color:var(--muted);font-family:var(--mono);font-size:.68rem">'
                    f'{row["jobs_found"]} found &middot; {row["new_jobs"]} new &middot; {ts}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="note info">No scrapes yet. Click Start above.</div>',
                unsafe_allow_html=True,
            )

    with col_r:
        st.markdown('<div class="slabel">Daily progress</div>', unsafe_allow_html=True)
        limit = int(db.load_settings().get("daily_limit","10"))
        applied_today = sum(
            1 for j in db.get_jobs(status="applied")
            if j.get("applied_at","")[:10] == datetime.now().strftime("%Y-%m-%d")
        )
        pct = min(1.0, applied_today / max(limit, 1))
        bar_col = "var(--green)" if pct < 0.8 else "var(--amber)"
        st.markdown(f"""
        <div class="scard" style="text-align:left;padding:15px 17px">
          <div style="display:flex;justify-content:space-between;margin-bottom:9px">
            <span style="font-size:.8rem">Applications today</span>
            <span style="font-family:var(--mono);font-size:.8rem;
                         color:var(--amber)">{applied_today} / {limit}</span>
          </div>
          <div class="bar-wrap">
            <div class="bar-fill" style="width:{pct*100:.0f}%;background:{bar_col}"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="slabel">Top matches today</div>', unsafe_allow_html=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        top = sorted(
            [j for j in db.get_jobs(min_score=50)
             if j.get("scraped_at","")[:10] == today_str],
            key=lambda x: x.get("match_score",0), reverse=True,
        )[:6]
        if top:
            for j in top:
                s = j.get("match_score",0)
                sc = "hi" if s >= 70 else ("mid" if s >= 50 else "lo")
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:4px 0;border-bottom:1px solid var(--border);font-size:.78rem">'
                    f'<span style="color:var(--text2)">{j["title"][:36]}</span>'
                    f'<span class="sc {sc}" style="position:static;font-size:.72rem">{s}%</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="note info">Run a scrape to see matches.</div>',
                unsafe_allow_html=True,
            )


def _stat(col, value, label, color):
    with col:
        st.markdown(f"""
        <div class="scard">
          <div class="sn" style="color:{color}">{value}</div>
          <div class="sl">{label}</div>
        </div>""", unsafe_allow_html=True)


# ==========================================================================
#  TAB 2 — JOBS BROWSER

def tab_jobs():
    cf1, cf2, cf3 = st.columns([2.5, 1.1, 1.1])
    with cf1:
        q = st.text_input("Search", placeholder="title, company, keyword...",
                          label_visibility="collapsed")
    with cf2:
        status_f = st.selectbox(
            "Status", ["all","new","pending_approval","applied","skipped"],
            label_visibility="collapsed",
        )
    with cf3:
        min_s = st.slider("Min %", 0, 100, 0, label_visibility="collapsed")

    jobs = db.get_jobs(status=status_f, search=q, min_score=min_s)
    st.markdown(
        f'<div style="font-size:.7rem;color:var(--muted);margin:.4rem 0">'
        f'{len(jobs)} results</div>',
        unsafe_allow_html=True,
    )

    for job in jobs:
        _job_card(job)


def _job_card(job: dict):
    score   = job.get("match_score", 0)
    status  = job.get("status", "new")
    sc_cls  = "hi" if score >= 70 else ("mid" if score >= 50 else "lo")
    card_cls = {"new":"new","pending_approval":"pend",
                "applied":"applied","skipped":"skipped"}.get(status,"new")
    pill_txt = status.replace("_"," ")

    st.markdown(f"""
    <div class="jcard {card_cls}">
      <span class="sc {sc_cls}">{score}%</span>
      <p class="jtitle">{job['title']}</p>
      <p class="jcompany">{job.get('company','') or 'Company not listed'}</p>
      <div class="jmeta">
        <span class="badge">{job.get('source','')}</span>
        <span>{job.get('location','Kenya')}</span>
        <span>{job.get('posted_date','')[:10]}</span>
        <span class="pill {card_cls}">{pill_txt}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"Details — {job['title'][:44]}"):
        # Show JD if available
        if job.get("description"):
            st.markdown('<div class="slabel">Job description</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="cvbox">{job["description"][:2500]}</div>',
                unsafe_allow_html=True,
            )

        ca, cb, cc, cd = st.columns(4)
        with ca:
            if st.button("Add to review queue", key=f"ap_{job['id']}", use_container_width=True):
                db.update_status(job["id"], "pending_approval")
                st.success("Added to Tailor tab")
                st.rerun()
        with cb:
            if st.button("Skip", key=f"sk_{job['id']}", use_container_width=True):
                db.update_status(job["id"], "skipped")
                st.rerun()
        with cc:
            if job.get("url"):
                st.link_button("Open posting", job["url"], use_container_width=True)
        with cd:
            if st.button("Notify Telegram", key=f"nt_{job['id']}", use_container_width=True):
                ok = notifier.send_job_alert(
                    job["id"], job["title"], job.get("company",""),
                    score, [], job.get("url",""),
                )
                st.success("Sent") if ok else st.error("Telegram not configured")


# ==========================================================================
#  TAB 3 — TAILOR + ANALYSE

def tab_tailor():
    cv = st.session_state.cv
    if not cv:
        st.markdown(
            '<div class="note warn">Upload your CV in the sidebar to enable AI analysis.</div>',
            unsafe_allow_html=True,
        )
        return

    # Manual job paste
    with st.expander("Paste a job manually"):
        p1, p2 = st.columns(2)
        with p1:
            m_title   = st.text_input("Job title",   key="man_title")
            m_company = st.text_input("Company",     key="man_co")
        with p2:
            m_url     = st.text_input("Job URL",     key="man_url")
            m_email   = st.text_input("Recruiter email (if known)", key="man_email")
        m_jd = st.text_area("Full job description", height=150, key="man_jd")
        if st.button("Add and queue for review", type="primary", key="man_add"):
            if m_title and m_jd:
                from modules.scrapers._utils import make_job as _make
                job_d = _make(title=m_title, company=m_company, url=m_url,
                              description=m_jd, source="Manual")
                if job_d:
                    inserted = db.insert_job(job_d)
                    matches  = db.get_jobs(search=m_title)
                    job_obj  = matches[0] if matches else None
                    if job_obj:
                        db.update_status(job_obj["id"], "pending_approval")
                    st.success("Added and queued for review")
                    st.rerun()
                else:
                    st.warning("Job title did not pass relevance filter. Check the title matches a tech/data role.")
            else:
                st.warning("Title and job description are required.")

    pending = db.get_jobs(status="pending_approval")

    if not pending:
        st.markdown(
            '<div class="note info">No jobs in the review queue. '
            'Approve jobs from the Jobs tab, or paste one above.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div class="slabel">{len(pending)} jobs awaiting your decision</div>',
        unsafe_allow_html=True,
    )

    for job in pending:
        score   = job.get("match_score", 0)
        sc_cls  = "hi" if score >= 70 else ("mid" if score >= 50 else "lo")

        with st.expander(
            f"{job['title']}  at  {job.get('company','?')}  —  {score}% pre-filter",
            expanded=(score >= 55),
        ):
            # Show JD prominently so user can read it before approving
            if job.get("description"):
                st.markdown('<div class="slabel">Job description</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="cvbox">{job["description"][:3000]}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="slabel">AI analysis</div>', unsafe_allow_html=True)

            if st.button("Analyse with Groq LLaMA", key=f"gen_{job['id']}"):
                if not config.GROQ_API_KEY:
                    st.error("GROQ_API_KEY not set in .env — free at console.groq.com")
                else:
                    with st.spinner("Groq is reading the JD and comparing to your profile..."):
                        result = analyzer.analyse(
                            job_title       = job["title"],
                            company         = job.get("company",""),
                            job_description = job.get("description",""),
                            url             = job.get("url",""),
                            source          = job.get("source",""),
                            cv_text         = cv.get("raw_text",""),
                            cv_skills       = cv.get("skills",[]),
                        )
                    db.update_job(
                        job["id"],
                        match_score    = result["match_score"],
                        keywords       = ", ".join(result.get("matched_keywords",[])[:12]),
                        missing_skills = ", ".join(result.get("missing_skills",[])[:10]),
                        tailored_cv    = result.get("tailored_cv_summary",""),
                        cover_letter   = result.get("cover_letter",""),
                    )
                    # Update Telegram with real score if above threshold
                    s = db.load_settings()
                    threshold = int(s.get("min_match_score", str(config.ATS_ALERT_THRESHOLD)))
                    if result["match_score"] >= threshold:
                        notifier.send_job_alert(
                            job["id"], job["title"], job.get("company",""),
                            result["match_score"],
                            result.get("missing_skills",[]),
                            job.get("url",""),
                        )
                    st.rerun()

            # Show analysis results if done
            if job.get("tailored_cv") or job.get("cover_letter"):
                _render_analysis(job)

            # Action row
            st.markdown("---")
            ba, bb, bc = st.columns(3)
            with ba:
                if st.button("Mark as applied", key=f"done_{job['id']}",
                             type="primary", use_container_width=True):
                    db.update_status(job["id"], "applied")
                    # Auto-export Excel
                    try:
                        excel_export.export_to_excel(db.get_jobs())
                    except Exception:
                        pass
                    st.success("Marked as applied — Excel updated")
                    st.rerun()
            with bb:
                if st.button("Skip", key=f"sk2_{job['id']}", use_container_width=True):
                    db.update_status(job["id"], "skipped")
                    st.rerun()
            with bc:
                if job.get("url"):
                    st.link_button("Open job URL", job["url"], use_container_width=True)


def _render_analysis(job: dict):
    score   = job.get("match_score", 0)
    sc_cls  = "hi" if score >= 70 else ("mid" if score >= 50 else "lo")

    # Score bar
    bar_col = "var(--green)" if score >= 70 else ("var(--yellow)" if score >= 50 else "var(--muted)")
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin:8px 0 12px">
      <span class="sc {sc_cls}" style="position:static;font-size:.88rem">{score}%</span>
      <div class="bar-wrap" style="flex:1">
        <div class="bar-fill" style="width:{score}%;background:{bar_col}"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Keywords
    col_a, col_b = st.columns(2)
    with col_a:
        if job.get("keywords"):
            kws = "".join(
                f'<span class="kw m">{k.strip()}</span>'
                for k in job["keywords"].split(",") if k.strip()
            )
            st.markdown(
                f'<div style="font-size:.65rem;color:var(--muted);margin-bottom:3px">Matched</div>'
                f'{kws}',
                unsafe_allow_html=True,
            )
    with col_b:
        if job.get("missing_skills"):
            mks = "".join(
                f'<span class="kw x">{s.strip()}</span>'
                for s in job["missing_skills"].split(",") if s.strip()
            )
            st.markdown(
                f'<div style="font-size:.65rem;color:var(--muted);margin-bottom:3px">Gaps</div>'
                f'{mks}',
                unsafe_allow_html=True,
            )

    # Tailored CV summary
    if job.get("tailored_cv"):
        st.markdown('<div class="slabel">Tailored summary</div>', unsafe_allow_html=True)
        edited_cv = st.text_area(
            "Edit if needed", value=job["tailored_cv"],
            height=110, key=f"cved_{job['id']}",
        )
        if edited_cv != job.get("tailored_cv"):
            db.update_job(job["id"], tailored_cv=edited_cv)

    # Cover letter
    if job.get("cover_letter"):
        st.markdown('<div class="slabel">Cover letter</div>', unsafe_allow_html=True)
        edited_cl = st.text_area(
            "Edit if needed", value=job["cover_letter"],
            height=240, key=f"cled_{job['id']}",
        )
        if edited_cl != job.get("cover_letter"):
            db.update_job(job["id"], cover_letter=edited_cl)

    # PDF generation
    cv = st.session_state.cv
    if not cv:
        return

    st.markdown('<div class="slabel">Generate documents</div>', unsafe_allow_html=True)
    pg1, pg2, pg3 = st.columns(3)

    with pg1:
        if st.button("Generate resume PDF", key=f"rpdf_{job['id']}", use_container_width=True):
            try:
                contact = {**cv.get("contact",{}), "name": config.YOUR_NAME}
                rpath   = generator.generate_resume(
                    contact=contact,
                    cv_sections=cv.get("sections",{}),
                    cv_skills=cv.get("skills",[]),
                    tailored_summary=job.get("tailored_cv",""),
                    tailored_bullets=[],
                    job_title=job["title"],
                    job_id=job["id"],
                )
                db.update_job(job["id"], resume_pdf_path=str(rpath))
                with open(rpath,"rb") as f:
                    st.download_button(
                        "Download resume", f,
                        file_name=rpath.name, mime="application/pdf",
                        key=f"dl_r_{job['id']}",
                    )
            except Exception as e:
                st.error(f"Resume error: {e}")

    with pg2:
        if st.button("Generate cover letter PDF", key=f"cpdf_{job['id']}", use_container_width=True):
            cl_text = job.get("cover_letter","")
            if not cl_text:
                st.warning("Run analysis first to generate a cover letter.")
            else:
                try:
                    contact = {**cv.get("contact",{}), "name": config.YOUR_NAME}
                    clpath  = generator.generate_cover_letter(
                        contact=contact,
                        job_title=job["title"],
                        company=job.get("company",""),
                        cover_letter_text=cl_text,
                        job_id=job["id"],
                    )
                    db.update_job(job["id"], cover_letter_pdf_path=str(clpath))
                    with open(clpath,"rb") as f:
                        st.download_button(
                            "Download cover letter", f,
                            file_name=clpath.name, mime="application/pdf",
                            key=f"dl_c_{job['id']}",
                        )
                except Exception as e:
                    st.error(f"Cover letter error: {e}")

    with pg3:
        if st.button("Notify via Telegram", key=f"ntfy_{job['id']}", use_container_width=True):
            ok = notifier.send_job_alert(
                job["id"], job["title"], job.get("company",""),
                job.get("match_score",0),
                job.get("missing_skills","").split(","),
                job.get("url",""),
            )
            st.success("Alert sent") if ok else st.error("Configure Telegram first")


# ==========================================================================
#  TAB 4 — APPLICATIONS TRACKER

def tab_applications():
    applied = db.get_jobs(status="applied")
    today   = datetime.now().strftime("%Y-%m-%d")
    wk_ago  = (datetime.now() - timedelta(days=7)).isoformat()

    t_today = sum(1 for j in applied if j.get("applied_at","")[:10] == today)
    t_week  = sum(1 for j in applied if j.get("applied_at","") >= wk_ago)

    c1, c2, c3 = st.columns(3)
    _stat(c1, t_today,      "Today",     "var(--teal)")
    _stat(c2, t_week,       "This week", "var(--amber)")
    _stat(c3, len(applied), "All time",  "var(--green)")

    st.markdown("<br>", unsafe_allow_html=True)

    # Export button
    col_exp, _ = st.columns([1,3])
    with col_exp:
        if st.button("Export to Excel", use_container_width=True):
            try:
                path = excel_export.export_to_excel(db.get_jobs())
                with open(path,"rb") as f:
                    st.download_button(
                        "Download Excel file", f,
                        file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            except Exception as e:
                st.error(f"Export error: {e}")

    st.markdown('<div class="slabel">Application log</div>', unsafe_allow_html=True)

    if not applied:
        st.markdown(
            '<div class="note info">No applications yet. Mark jobs as applied in the Tailor tab.</div>',
            unsafe_allow_html=True,
        )
        return

    for j in applied:
        d  = j.get("applied_at","")[:10]
        sc = j.get("match_score",0)
        sc_cls = "hi" if sc >= 70 else ("mid" if sc >= 50 else "lo")
        st.markdown(f"""
        <div class="jcard applied">
          <span class="sc {sc_cls}">{sc}%</span>
          <p class="jtitle">{j['title']}</p>
          <p class="jcompany">{j.get('company','')}</p>
          <div class="jmeta">
            <span class="badge">{j.get('source','')}</span>
            <span>Applied {d}</span>
            <span>{j.get('location','')}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)


# ==========================================================================
#  TAB 5 — LOGS

def tab_logs():
    logs = db.get_scrape_log(60)
    st.markdown('<div class="slabel">Scrape log</div>', unsafe_allow_html=True)

    if logs:
        lines = "\n".join(
            f"[{r['timestamp'][:16]}]  {r['source']:<18}  "
            f"found:{r['jobs_found']:<4}  new:{r['new_jobs']:<4}  {r['status']}"
            + (f"  {r['message'][:55]}" if r.get("message") else "")
            for r in logs
        )
        st.markdown(f'<div class="log">{lines}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="note info">No scrape history. Run a scrape from the Dashboard.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="slabel">Database actions</div>', unsafe_allow_html=True)
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        if st.button("Clear skipped jobs", use_container_width=True):
            import sqlite3
            with sqlite3.connect(str(config.DB_PATH)) as c:
                n = c.execute("DELETE FROM jobs WHERE status='skipped'").rowcount
            st.success(f"Cleared {n} jobs")
    with dc2:
        if st.button("Reset all to new", use_container_width=True):
            import sqlite3
            with sqlite3.connect(str(config.DB_PATH)) as c:
                c.execute("UPDATE jobs SET status='new', notification_sent=0 "
                          "WHERE status NOT IN ('applied')")
            st.success("Reset complete")
    with dc3:
        if st.button("Export Excel now", use_container_width=True):
            try:
                path = excel_export.export_to_excel(db.get_jobs())
                with open(path,"rb") as f:
                    st.download_button(
                        "Download", f, file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            except Exception as e:
                st.error(str(e))


# ==========================================================================
#  TAB 6 — SETTINGS

def tab_settings():
    s = db.load_settings()

    st.markdown('<div class="slabel">Search preferences</div>', unsafe_allow_html=True)
    user_kws = st.text_area(
        "Custom keywords (comma-separated, leave blank for defaults)",
        value=s.get("user_keywords",""),
        height=80,
        help="e.g. data engineer, power bi, airflow, fastapi",
    )
    max_days = st.slider("Only include jobs posted within N days", 1, 30,
                          int(s.get("max_days","7")))

    st.markdown('<div class="slabel">Notification settings</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        groq_key   = st.text_input("Groq API key",     value=s.get("groq_key",""),  type="password")
        tg_token   = st.text_input("Telegram token",   value=s.get("telegram_token",""), type="password")
        tg_chat    = st.text_input("Telegram chat ID", value=s.get("telegram_chat_id",""))
    with col2:
        wa_hook    = st.text_input("WhatsApp webhook URL",
                                    value=s.get("whatsapp_webhook",""),
                                    placeholder="https://your-bot.example.com/webhook")
        threshold  = st.slider("Alert threshold (min score)", 0, 100,
                                int(s.get("min_match_score", str(config.ATS_ALERT_THRESHOLD))), 5)
        daily_lim  = st.number_input("Max applications per day", 1, 50,
                                      int(s.get("daily_limit","10")))

    st.markdown('<div class="slabel">Aiven PostgreSQL (optional)</div>', unsafe_allow_html=True)
    pg_url = st.text_input(
        "Aiven DATABASE_URL",
        value=s.get("pg_url",""),
        type="password",
        placeholder="postgresql://user:pass@host:port/dbname?sslmode=require",
        help="Leave blank to use local SQLite only",
    )

    if st.button("Save all settings", type="primary"):
        db.save_settings({
            "user_keywords":     user_kws,
            "max_days":          str(max_days),
            "groq_key":          groq_key,
            "telegram_token":    tg_token,
            "telegram_chat_id":  tg_chat,
            "whatsapp_webhook":  wa_hook,
            "min_match_score":   str(threshold),
            "daily_limit":       str(daily_lim),
            "pg_url":            pg_url,
        })
        st.success("Settings saved — restart the app if you changed the Groq key or DATABASE_URL")

    st.markdown('<div class="slabel">Quick setup guide</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="note info">
    <strong>5-minute setup</strong><br><br>
    1. <strong>Groq</strong> (free, fast): console.groq.com &rarr; API Keys &rarr; create &rarr; paste above or in .env<br>
    2. <strong>Playwright</strong>: after pip install, run <code>playwright install chromium</code> once<br>
    3. <strong>Telegram bot</strong>: @BotFather &rarr; /newbot &rarr; copy token. Then message your bot once.<br>
       Get your chat ID from: <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code><br>
    4. <strong>WhatsApp</strong>: set WHATSAPP_WEBHOOK_URL to your custom bot endpoint.<br>
       JobScout will POST <code>{"job_id","title","company","score","url"}</code> to it on every alert.<br>
    5. <strong>Aiven PostgreSQL</strong>: create a free PostgreSQL service at aiven.io,
       copy the Service URI and paste above. All new jobs mirror there automatically.<br>
    6. <strong>Excel</strong>: click Export anytime, or it auto-updates when you mark a job as applied.
    </div>
    """, unsafe_allow_html=True)


# ==========================================================================
#  HELPERS


def _run_scrape(sources: list, keywords, max_days: int):
    log_box = st.empty()
    prog    = st.progress(0)
    lines   = []

    def log(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        lines.append(f"[{ts}]  {msg}")
        log_box.markdown(
            f'<div class="log">{"<br>".join(lines[-12:])}</div>',
            unsafe_allow_html=True,
        )

    log("Starting scrape session...")
    result    = scrapers.run_scrapers(
        sources=sources, keywords=keywords,
        max_days=max_days, progress_fn=log,
    )
    prog.progress(1.0)
    total_new = result["total_new"]
    log(f"Complete — {total_new} new relevant jobs found.")

    # Auto-notify high-scoring new jobs
    if total_new > 0 and notifier.is_tg_configured():
        s         = db.load_settings()
        threshold = int(s.get("min_match_score", str(config.ATS_ALERT_THRESHOLD)))
        to_notify = [
            j for j in db.get_jobs(status="new", min_score=threshold)
            if not j.get("notification_sent")
        ][:8]
        sent = 0
        for j in to_notify:
            ok = notifier.send_job_alert(
                j["id"], j["title"], j.get("company",""),
                j.get("match_score",0), [], j.get("url",""),
            )
            if ok:
                db.update_job(j["id"], notification_sent=1, status="pending_approval")
                sent += 1
            time.sleep(0.4)
        if sent:
            log(f"Sent {sent} Telegram alerts for high-scoring matches.")

    parts = [f"{k}: {v['new']} new" for k,v in result['sources'].items() if v['status']=='ok']
    st.success(
        f"Found {total_new} new jobs across {len(result['sources'])} sources. "
        + ", ".join(parts)
    )
    time.sleep(0.8)
    st.rerun()


def _process_callbacks():
    callbacks = notifier.poll_callbacks()
    if not callbacks:
        st.info("No pending Telegram responses.")
        return
    for cb in callbacks:
        action = cb["action"]
        jid    = cb["job_id"]
        if action == "approve":
            db.update_status(jid, "pending_approval")
            st.success(f"Job #{jid} approved via Telegram — now in Tailor tab")
        elif action == "ignore":
            db.update_status(jid, "skipped")
            st.info(f"Job #{jid} skipped via Telegram")


# ==========================================================================
#  MAIN

def main():
    render_topbar()
    render_sidebar()

    tabs = st.tabs([
        "Dashboard",
        "Jobs",
        "Tailor + Analyse",
        "Applications",
        "Logs",
        "Settings",
    ])

    with tabs[0]: tab_dashboard()
    with tabs[1]: tab_jobs()
    with tabs[2]: tab_tailor()
    with tabs[3]: tab_applications()
    with tabs[4]: tab_logs()
    with tabs[5]: tab_settings()


if __name__ == "__main__":
    main()

# run with `streamlit run app.py`