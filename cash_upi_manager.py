import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# =========================================================
# APP CONFIG & INITIALIZATION
# =========================================================
st.set_page_config(
    page_title="Vault | Mobile Money",
    page_icon="🏦",
    layout="centered",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "cash_upi_money_manager.db"

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True 
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Home"


# =========================================================
# DATABASE (Core Logic Retained)
# =========================================================
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tx_date TEXT NOT NULL, tx_type TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0), wallet TEXT, from_wallet TEXT, to_wallet TEXT,
            person TEXT, category TEXT, due_date TEXT, note TEXT DEFAULT '', created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fds (
            id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT NOT NULL, amount REAL NOT NULL CHECK(amount > 0),
            interest_rate REAL DEFAULT 0, maturity_date TEXT, bank_name TEXT DEFAULT '',
            note TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# =========================================================
# DATA HELPERS
# =========================================================
def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def fmt_money(value): return f"₹{float(value):,.2f}"
def fmt_compact(value):
    v, sign = abs(float(value)), "-" if float(value) < 0 else ""
    if v >= 1_00_00_000: return f"{sign}₹{v/1_00_00_000:.2f}Cr"
    if v >= 1_00_000: return f"{sign}₹{v/1_00_000:.2f}L"
    if v >= 1_000: return f"{sign}₹{v/1_000:.1f}k"
    return f"{sign}₹{v:,.0f}"

def execute(sql, params=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

def query(sql, params=()):
    conn = get_db()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

def get_balance(wallet):
    q = "SELECT COALESCE(SUM(amount),0) AS n FROM transactions WHERE tx_type=? AND {}"
    inc = query(q.format("wallet=?"), ('Income', wallet)).iloc[0]['n']
    op = query(q.format("wallet=?"), ('Opening Balance', wallet)).iloc[0]['n']
    exp = query(q.format("wallet=?"), ('Expense', wallet)).iloc[0]['n']
    t_in = query(q.format("to_wallet=?"), ('Transfer', wallet)).iloc[0]['n']
    t_out = query(q.format("from_wallet=?"), ('Transfer', wallet)).iloc[0]['n']
    gvn = query(q.format("wallet=?"), ('Money Given', wallet)).iloc[0]['n']
    rtn = query(q.format("wallet=?"), ('Money Returned', wallet)).iloc[0]['n']
    fd_c = query(q.format("wallet=?"), ('FD Created', wallet)).iloc[0]['n']
    fd_m = query(q.format("wallet=?"), ('FD Matured', wallet)).iloc[0]['n']
    fd_i = query(q.format("wallet=?"), ('FD Interest Payout', wallet)).iloc[0]['n']
    return float(op + inc - exp + t_in - t_out - gvn + rtn - fd_c + fd_m + fd_i)

def pending_summary():
    df = query("""
        SELECT person,
        SUM(CASE WHEN tx_type='Money Given' THEN amount ELSE 0 END) AS given,
        SUM(CASE WHEN tx_type='Money Returned' THEN amount ELSE 0 END) AS returned
        FROM transactions WHERE person IS NOT NULL AND TRIM(person) <> '' GROUP BY person
    """)
    if not df.empty: df["pending"] = (df["given"] - df["returned"]).clip(lower=0)
    return df

# =========================================================
# MOBILE UI THEME & CSS ENGINE
# =========================================================
DARK_THEME = {
    "bg": "#000000", "surface": "#121212", "surface2": "#1E1E1E", "text": "#FFFFFF",
    "subtext": "#A0A0A5", "border": "#2C2C2E", "primary": "#0A84FF",
    "pos": "#30D158", "neg": "#FF453A", "accent": "#FF9F0A"
}
LIGHT_THEME = {
    "bg": "#F2F2F7", "surface": "#FFFFFF", "surface2": "#F9F9EB", "text": "#1C1C1E",
    "subtext": "#8E8E93", "border": "#E5E5EA", "primary": "#007AFF",
    "pos": "#34C759", "neg": "#FF3B30", "accent": "#FF9500"
}
T = DARK_THEME if st.session_state.dark_mode else LIGHT_THEME

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {{ font-family: 'Inter', -apple-system, sans-serif; background-color: {T['bg']}; }}
    .stApp {{ background-color: {T['bg']}; }}
    .block-container {{ padding: 1rem 1rem 6rem 1rem !important; max-width: 500px; margin: 0 auto; }}
    header, footer, #MainMenu {{ display: none !important; }}

    /* Mobile App Header */
    .app-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
    .app-title {{ font-size: 24px; font-weight: 800; color: {T['text']}; letter-spacing: -0.5px; }}
    
    /* Main Balance Card (Glassmorphism) */
    .balance-card {{
        background: linear-gradient(135deg, {T['surface2']} 0%, {T['surface']} 100%);
        border: 1px solid {T['border']}; border-radius: 24px; padding: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 16px;
    }}
    .balance-label {{ font-size: 13px; color: {T['subtext']}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
    .balance-amount {{ font-size: 42px; font-weight: 800; color: {T['text']}; letter-spacing: -1px; margin: 4px 0 16px 0; }}
    .wallet-split {{ display: flex; gap: 12px; }}
    .wallet-pill {{ background: {T['bg']}; border-radius: 12px; padding: 10px 14px; flex: 1; border: 1px solid {T['border']}; }}
    .wallet-pill-label {{ font-size: 12px; color: {T['subtext']}; font-weight: 500; margin-bottom: 2px; }}
    .wallet-pill-val {{ font-size: 16px; color: {T['text']}; font-weight: 700; }}

    /* Fintech Style Lists */
    .list-header {{ font-size: 17px; font-weight: 700; color: {T['text']}; margin: 24px 0 12px 0; }}
    .tx-container {{ background: {T['surface']}; border-radius: 20px; overflow: hidden; border: 1px solid {T['border']}; }}
    .tx-row {{ display: flex; align-items: center; padding: 16px; border-bottom: 1px solid {T['border']}; }}
    .tx-row:last-child {{ border-bottom: none; }}
    .tx-icon {{ width: 40px; height: 40px; border-radius: 12px; display: flex; justify-content: center; align-items: center; font-size: 18px; margin-right: 14px; background: {T['bg']}; }}
    .tx-details {{ flex: 1; min-width: 0; }}
    .tx-title {{ font-size: 15px; font-weight: 600; color: {T['text']}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .tx-sub {{ font-size: 13px; color: {T['subtext']}; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .tx-amt {{ font-size: 16px; font-weight: 700; text-align: right; }}
    
    /* Colors */
    .c-pos {{ color: {T['pos']}; }} .bg-pos {{ background: {T['pos']}20; color: {T['pos']}; }}
    .c-neg {{ color: {T['text']}; }} .bg-neg {{ background: {T['surface2']}; color: {T['text']}; }}
    .c-acc {{ color: {T['accent']}; }} .bg-acc {{ background: {T['accent']}20; color: {T['accent']}; }}
    .c-pri {{ color: {T['primary']}; }} .bg-pri {{ background: {T['primary']}20; color: {T['primary']}; }}

    /* Streamlit overrides for Mobile feel */
    div[data-testid="stPills"] button {{ border-radius: 12px !important; font-weight: 600 !important; background: {T['surface']} !important; border: 1px solid {T['border']} !important; }}
    div[data-testid="stPills"] button[aria-selected="true"] {{ background: {T['text']} !important; color: {T['bg']} !important; }}
    
    .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {{
        background-color: {T['surface']} !important; border-radius: 12px !important; border: 1px solid {T['border']} !important; padding: 14px !important; font-size: 16px !important; color: {T['text']} !important;
    }}
    .stButton>button {{ border-radius: 16px !important; font-weight: 700 !important; padding: 14px !important; font-size: 16px !important; transition: transform 0.1s; }}
    .stButton>button:active {{ transform: scale(0.97); }}
    button[kind="primary"] {{ background-color: {T['primary']} !important; color: white !important; border: none !important; }}
    
    /* Empty State */
    .empty-state {{ text-align: center; padding: 40px 20px; color: {T['subtext']}; background: {T['surface']}; border-radius: 20px; border: 1px dashed {T['border']}; margin-top: 10px; }}
</style>
""", unsafe_allow_html=True)

# UI Component Helpers
TX_STYLES = {
    "Income": ("↓", "bg-pos", "c-pos", "+"), "Expense": ("↑", "bg-neg", "c-neg", ""),
    "Transfer": ("⇄", "bg-pri", "c-pri", ""), "Money Given": ("↗", "bg-neg", "c-neg", ""),
    "Money Returned": ("↙", "bg-pos", "c-pos", "+"), "FD Created": ("🏦", "bg-acc", "c-neg", ""),
    "FD Matured": ("🏦", "bg-pos", "c-pos", "+"), "FD Interest Payout": ("✦", "bg-pos", "c-pos", "+"),
    "Opening Balance": ("●", "bg-pri", "c-pri", "")
}

def render_tx_list(df, empty_msg="No activity yet."):
    if df.empty:
        st.markdown(f'<div class="empty-state">📝<br><br>{empty_msg}</div>', unsafe_allow_html=True)
        return
    
    html = '<div class="tx-container">'
    for _, r in df.iterrows():
        icon, bg_c, txt_c, sign = TX_STYLES.get(r['Type'], ("•", "bg-neg", "c-neg", ""))
        
        # Smart Title & Subtitle logic
        if r['Type'] == "Transfer": title = f"{r.get('From_Wallet','')} → {r.get('To_Wallet','')}"
        else: title = " · ".join(filter(None, [r.get('Category'), r.get('Person'), r['Type']]))
        
        sub_elements = [r['Date']]
        if r.get('Wallet') and r['Type'] != "Transfer": sub_elements.append(r['Wallet'])
        if r.get('Notes') or r.get('Note'): sub_elements.append((r.get('Notes') or r.get('Note')).strip())
        sub = " • ".join(sub_elements)

        html += f"""
        <div class="tx-row">
            <div class="tx-icon {bg_c}">{icon}</div>
            <div class="tx-details">
                <div class="tx-title">{title}</div>
                <div class="tx-sub">{sub}</div>
            </div>
            <div class="tx-amt {txt_c}">{sign}{fmt_compact(r['Amount'])}</div>
        </div>
        """
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def app_header():
    c1, c2 = st.columns([5,1])
    with c1: st.markdown('<div class="app-header"><div class="app-title">Vault.</div></div>', unsafe_allow_html=True)
    with c2: 
        if st.button("🌓", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    # Mobile Router / Navigation Tab
    tabs = ["Overview", "Transact", "Pending", "FDs", "More"]
    selected = st.pills("Nav", tabs, default=st.session_state.active_tab, label_visibility="collapsed")
    if selected and selected != st.session_state.active_tab:
        st.session_state.active_tab = selected
        st.rerun()

# =========================================================
# APP SCREENS (Pages)
# =========================================================

def page_overview():
    cash, upi = get_balance("Cash"), get_balance("UPI")
    total = cash + upi
    fd_total = float(query("SELECT COALESCE(SUM(amount),0) AS n FROM fds WHERE status='Active'").iloc[0]["n"])
    
    st.markdown(f"""
    <div class="balance-card">
        <div class="balance-label">Total Balance</div>
        <div class="balance-amount">{fmt_money(total)}</div>
        <div class="wallet-split">
            <div class="wallet-pill">
                <div class="wallet-pill-label">💵 Cash</div>
                <div class="wallet-pill-val">{fmt_compact(cash)}</div>
            </div>
            <div class="wallet-pill">
                <div class="wallet-pill-label">📱 UPI</div>
                <div class="wallet-pill-val">{fmt_compact(upi)}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if fd_total > 0:
        st.markdown(f"""
        <div class="wallet-pill" style="margin-bottom:16px; border: 1px solid {T['accent']}40;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div class="wallet-pill-label">🏦 Locked in Active FDs</div>
                    <div class="wallet-pill-val" style="color: {T['accent']}">{fmt_money(fd_total)}</div>
                </div>
                <div style="font-size:24px">🔒</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f'<div class="list-header">Recent Activity</div>', unsafe_allow_html=True)
    recent = query("SELECT id AS ID, tx_date AS Date, tx_type AS Type, amount AS Amount, wallet AS Wallet, from_wallet AS From_Wallet, to_wallet AS To_Wallet, person AS Person, category AS Category, note AS Note FROM transactions ORDER BY tx_date DESC, id DESC LIMIT 5")
    render_tx_list(recent, "Your recent transactions will appear here.")

def page_transact():
    st.markdown(f'<div class="list-header">New Transaction</div>', unsafe_allow_html=True)
    
    tx_type = st.pills("Type", ["Expense", "Income", "Transfer", "Lend/Borrow"], default="Expense", label_visibility="collapsed")
    
    with st.form("add_tx_form", clear_on_submit=True):
        amt = st.number_input("Amount (₹)", min_value=0.01, step=500.0, format="%.2f")
        
        # Dynamic form fields based on selection
        col1, col2 = st.columns(2)
        with col1: d = st.date_input("Date", date.today())
        
        from_w = to_w = wallet = cat = person = db_tx_type = None
        
        if tx_type == "Transfer":
            db_tx_type = "Transfer"
            with col2: from_w = st.selectbox("From", ["Cash", "UPI"])
            to_w = st.selectbox("To", ["UPI", "Cash"])
        
        elif tx_type == "Lend/Borrow":
            direction = st.radio("Action", ["I Gave Money ↗", "I Got Money Back ↙"], horizontal=True, label_visibility="collapsed")
            db_tx_type = "Money Given" if "Gave" in direction else "Money Returned"
            with col2: wallet = st.selectbox("Wallet Used", ["UPI", "Cash"])
            
            existing = query("SELECT DISTINCT person FROM transactions WHERE person IS NOT NULL AND TRIM(person) <> ''")['person'].tolist()
            p_sel = st.selectbox("Person", ["➕ New Person"] + existing)
            person = st.text_input("Name") if p_sel == "➕ New Person" else p_sel
            
        else:
            db_tx_type = tx_type
            with col2: wallet = st.selectbox("Wallet", ["UPI", "Cash"])
            cat = st.text_input("Category (e.g. Food, Salary)")
            
        note = st.text_input("Optional Note")
        
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button(f"Confirm {tx_type}", type="primary", use_container_width=True)
        
        if submitted:
            if amt <= 0: st.error("Amount must be positive.")
            elif tx_type == "Transfer" and from_w == to_w: st.error("Select different wallets.")
            elif tx_type == "Lend/Borrow" and not person: st.error("Name is required.")
            else:
                execute(
                    "INSERT INTO transactions (tx_date, tx_type, amount, wallet, from_wallet, to_wallet, person, category, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (d.isoformat(), db_tx_type, float(amt), wallet, from_w, to_w, (person or "").strip(), (cat or "").strip(), note.strip(), now())
                )
                st.success(f"Recorded ₹{amt:,.0f} successfully!")
                st.session_state.active_tab = "Overview"
                st.rerun()

def page_pending():
    st.markdown(f'<div class="list-header">IOU & Pending</div>', unsafe_allow_html=True)
    p = pending_summary()
    
    if p.empty or p['pending'].sum() == 0:
        st.markdown(f'<div class="empty-state">🤝<br><br>All settled up! No pending money.</div>', unsafe_allow_html=True)
    else:
        html = '<div class="tx-container">'
        for _, r in p[p['pending'] > 0].iterrows():
            html += f"""
            <div class="tx-row">
                <div class="tx-icon bg-neg">👤</div>
                <div class="tx-details">
                    <div class="tx-title">{r['person']}</div>
                    <div class="tx-sub">Given: {fmt_compact(r['given'])} • Got: {fmt_compact(r['returned'])}</div>
                </div>
                <div class="tx-amt" style="color:{T['neg']}">-{fmt_compact(r['pending'])}</div>
            </div>
            """
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        
        st.markdown(f'<div class="list-header" style="margin-top:32px;">Person History</div>', unsafe_allow_html=True)
        person = st.selectbox("Select Person", p["person"].tolist(), label_visibility="collapsed")
        detail = query("SELECT id AS ID, tx_date AS Date, tx_type AS Type, amount AS Amount, wallet AS Wallet, note AS Notes FROM transactions WHERE person=? ORDER BY tx_date DESC", (person,))
        render_tx_list(detail)

def page_fds():
    st.markdown(f'<div class="list-header">Fixed Deposits Vault</div>', unsafe_allow_html=True)
    
    active = query("SELECT id AS ID, start_date AS Date, amount AS Amount, interest_rate AS Rate, maturity_date AS Maturity, bank_name AS Bank, note AS Notes FROM fds WHERE status='Active' ORDER BY start_date DESC")
    
    if active.empty:
        st.markdown(f'<div class="empty-state">🏦<br><br>No active FDs. Build your savings here.</div>', unsafe_allow_html=True)
    else:
        html = '<div class="tx-container">'
        for _, r in active.iterrows():
            html += f"""
            <div class="tx-row" style="border-left: 4px solid {T['accent']};">
                <div class="tx-details">
                    <div class="tx-title" style="font-size: 18px;">{fmt_money(r['Amount'])}</div>
                    <div class="tx-sub">{r['Bank']} • {r['Rate']}% p.a. • Matures: {r['Maturity']}</div>
                </div>
                <div class="tx-amt" style="font-size:12px; font-weight:500; color:{T['subtext']}">ID #{r['ID']}</div>
            </div>
            """
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

    with st.expander("➕ Open New FD", expanded=active.empty):
        with st.form("fd_form", clear_on_submit=True):
            f_amt = st.number_input("Principal (₹)", min_value=100.0, step=5000.0)
            f_rate = st.number_input("Interest Rate (%)", value=7.0, step=0.1)
            f_bank = st.text_input("Bank Name")
            c1, c2 = st.columns(2)
            with c1: f_start = st.date_input("Start Date")
            with c2: f_end = st.date_input("Maturity Date")
            
            if st.form_submit_button("Lock Funds (from UPI)", type="primary", use_container_width=True):
                if f_amt > get_balance("UPI"): st.error("Insufficient UPI balance.")
                else:
                    execute("INSERT INTO fds (start_date, amount, interest_rate, maturity_date, bank_name, created_at) VALUES (?, ?, ?, ?, ?, ?)", (f_start.isoformat(), float(f_amt), float(f_rate), f_end.isoformat(), f_bank.strip(), now()))
                    execute("INSERT INTO transactions (tx_date, tx_type, amount, wallet, category, note, created_at) VALUES (?, 'FD Created', ?, 'UPI', 'Vault', ?, ?)", (f_start.isoformat(), float(f_amt), f"FD created at {f_bank}", now()))
                    st.success("FD Created!")
                    st.rerun()

    if not active.empty:
        with st.expander("📥 Log Monthly Interest"):
            with st.form("int_form", clear_on_submit=True):
                fd_id = st.selectbox("Select FD", active['ID'].tolist(), format_func=lambda x: f"FD #{x} - {active[active['ID']==x].iloc[0]['Bank']}")
                i_amt = st.number_input("Interest Amount (₹)", min_value=1.0)
                if st.form_submit_button("Credit Interest to UPI", use_container_width=True):
                    execute("INSERT INTO transactions (tx_date, tx_type, amount, wallet, category, note, created_at) VALUES (?, 'FD Interest Payout', ?, 'UPI', 'FD Return', ?, ?)", (date.today().isoformat(), float(i_amt), f"Monthly Interest for FD #{fd_id}", now()))
                    st.success("Interest Credited!")
                    st.rerun()
                    
        with st.expander("↩️ Mature & Close FD"):
            with st.form("close_form"):
                fd_id = st.selectbox("Select FD to Close", active['ID'].tolist())
                ret_amt = st.number_input("Principal Returned (₹)", min_value=1.0, value=float(active[active['ID']==fd_id].iloc[0]['Amount']))
                if st.form_submit_button("Mature FD (Credit to UPI)", use_container_width=True):
                    execute("UPDATE fds SET status='Matured' WHERE id=?", (int(fd_id),))
                    execute("INSERT INTO transactions (tx_date, tx_type, amount, wallet, category, note, created_at) VALUES (?, 'FD Matured', ?, 'UPI', 'Vault', ?, ?)", (date.today().isoformat(), float(ret_amt), f"FD #{fd_id} Matured", now()))
                    st.success("FD Closed and credited to UPI!")
                    st.rerun()

def page_more():
    st.markdown(f'<div class="list-header">Complete Ledger</div>', unsafe_allow_html=True)
    df = query("SELECT id AS ID, tx_date AS Date, tx_type AS Type, amount AS Amount, wallet AS Wallet, from_wallet AS From_Wallet, to_wallet AS To_Wallet, person AS Person, category AS Category, note AS Notes FROM transactions ORDER BY tx_date DESC, id DESC")
    render_tx_list(df)

    st.markdown(f'<div class="list-header" style="margin-top:32px;">Danger Zone</div>', unsafe_allow_html=True)
    if not df.empty:
        with st.expander("🗑️ Delete a Transaction"):
            tx_id = st.selectbox("Select ID to Delete", df["ID"].tolist(), format_func=lambda i: f"#{i} — {df.loc[df['ID']==i,'Type'].values[0]} — {fmt_money(df.loc[df['ID']==i,'Amount'].values[0])}")
            if st.button("Delete Permanently", use_container_width=True):
                execute("DELETE FROM transactions WHERE id=?", (int(tx_id),))
                st.success("Deleted.")
                st.rerun()

# =========================================================
# APP ROUTER
# =========================================================
app_header()

if st.session_state.active_tab == "Overview": page_overview()
elif st.session_state.active_tab == "Transact": page_transact()
elif st.session_state.active_tab == "Pending": page_pending()
elif st.session_state.active_tab == "FDs": page_fds()
elif st.session_state.active_tab == "More": page_more()
