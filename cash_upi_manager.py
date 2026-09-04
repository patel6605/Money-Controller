import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(
    page_title="Cash & UPI Money Manager",
    page_icon="💰",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "cash_upi_money_manager.db"


# =========================================================
# DATABASE
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT NOT NULL,
            tx_type TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            wallet TEXT,
            from_wallet TEXT,
            to_wallet TEXT,
            person TEXT,
            category TEXT,
            due_date TEXT,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            interest_rate REAL DEFAULT 0,
            maturity_date TEXT,
            bank_name TEXT DEFAULT '',
            note TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# HELPERS
# =========================================================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def money(value):
    return f"₹{float(value):,.2f}"


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


def wallet_balance(wallet):
    """Available money currently in Cash or UPI."""
    income = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='Income' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    opening = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='Opening Balance' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    expense = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='Expense' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    transfer_in = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='Transfer' AND to_wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    transfer_out = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='Transfer' AND from_wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    given = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='Money Given' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    returned = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='Money Returned' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    fd_created = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='FD Created' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    fd_returned = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='FD Matured' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]
    
    fd_interest = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM transactions "
        "WHERE tx_type='FD Interest Payout' AND wallet=?",
        (wallet,),
    ).iloc[0]["n"]

    return float(
        opening + income - expense
        + transfer_in - transfer_out
        - given + returned
        - fd_created + fd_returned + fd_interest
    )


def pending_summary():
    df = query("""
        SELECT
            person,
            SUM(CASE WHEN tx_type='Money Given'
                     THEN amount ELSE 0 END) AS given,
            SUM(CASE WHEN tx_type='Money Returned'
                     THEN amount ELSE 0 END) AS returned
        FROM transactions
        WHERE person IS NOT NULL AND TRIM(person) <> ''
        GROUP BY person
        ORDER BY person COLLATE NOCASE
    """)
    if df.empty:
        return df

    df["pending"] = (df["given"] - df["returned"]).clip(lower=0)
    return df


def active_fd_total():
    row = query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM fds WHERE status='Active'"
    ).iloc[0]
    return float(row["n"])


def total_pending():
    p = pending_summary()
    return float(p["pending"].sum()) if not p.empty else 0.0


def people():
    df = query("""
        SELECT DISTINCT person
        FROM transactions
        WHERE person IS NOT NULL AND TRIM(person) <> ''
        ORDER BY person COLLATE NOCASE
    """)
    return df["person"].tolist() if not df.empty else []


# =========================================================
# STYLE (VISUALLY CLEAR IN LIGHT & DARK MODE)
# =========================================================
if "dark" not in st.session_state:
    st.session_state.dark = False  # Default to Light mode for sharp initial clarity

if st.session_state.dark:
    bg = "#0b1020"
    card = "#141c2e"
    card_border = "rgba(128,145,180,.25)"
    text = "#f5f7ff"
    muted = "#aab5ca"
    table_bg = "#141c2e"
else:
    bg = "#f8fafc"
    card = "#ffffff"
    card_border = "#cbd5e1"
    text = "#0f172a"
    muted = "#475569"
    table_bg = "#ffffff"

st.markdown(
    f"""
    <style>
    .stApp {{ background:{bg}; color:{text}; }}
    [data-testid="stSidebar"] {{ background:{card}; border-right: 1px solid {card_border}; }}
    [data-testid="stSidebar"] * {{ color:{text} !important; }}
    .title {{ font-size:32px; font-weight:800; color:{text}; }}
    .subtitle {{ color:{muted}; margin-bottom:20px; font-size:15px; }}
    .card {{
        background:{card};
        border:1px solid {card_border};
        border-radius:14px;
        padding:20px;
        margin-bottom:12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    /* Ensure metric text and labels are high contrast */
    [data-testid="stMetricValue"] {{ color: {text} !important; }}
    [data-testid="stMetricLabel"] {{ color: {muted} !important; font-weight: 600 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HEADER
# =========================================================
top1, top2 = st.columns([7, 1])
with top1:
    st.markdown('<div class="title">💰 Cash & UPI Money Manager</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Cash + UPI • Internal Transfers • Pending Money • Monthly FD Interest to UPI</div>',
        unsafe_allow_html=True,
    )
with top2:
    label = "🌙 Dark" if not st.session_state.dark else "☀️ Light"
    if st.button(label, use_container_width=True):
        st.session_state.dark = not st.session_state.dark
        st.rerun()


# =========================================================
# NAVIGATION
# =========================================================
st.sidebar.title("Menu")
page = st.sidebar.radio(
    "Open",
    [
        "🏠 Dashboard",
        "➕ Add Transaction",
        "⏳ Pending Money",
        "🏦 Fixed Deposits",
        "📊 Reports",
        "📋 History",
    ],
)

st.sidebar.divider()
st.sidebar.caption("Only Cash and UPI are active transaction wallets.")
st.sidebar.caption("Cash ↔ UPI transfers do not change combined totals.")


# =========================================================
# DASHBOARD
# =========================================================
if page == "🏠 Dashboard":
    cash = wallet_balance("Cash")
    upi = wallet_balance("UPI")
    available = cash + upi
    pending = total_pending()
    fd_total = active_fd_total()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Cash Total", money(cash))
    c2.metric("📱 UPI Total", money(upi))
    c3.metric("💰 Cash + UPI", money(available))
    c4.metric("⏳ Pending Money", money(pending))

    st.metric("🏦 Active FD Principal", money(fd_total))

    st.markdown("### Overview Breakdown")
    a, b, c = st.columns(3)
    with a:
        st.markdown(
            f'<div class="card"><b>Cash Wallet</b><br><span style="font-size:20px; font-weight:700;">{money(cash)}</span><br>'
            f'<small style="color:{muted};">Available physical cash on hand.</small></div>',
            unsafe_allow_html=True,
        )
    with b:
        st.markdown(
            f'<div class="card"><b>UPI Wallet</b><br><span style="font-size:20px; font-weight:700;">{money(upi)}</span><br>'
            f'<small style="color:{muted};">Available digital/UPI bank balance.</small></div>',
            unsafe_allow_html=True,
        )
    with c:
        st.markdown(
            f'<div class="card"><b>Pending Outflow</b><br><span style="font-size:20px; font-weight:700;">{money(pending)}</span><br>'
            f'<small style="color:{muted};">Money given out, awaiting return.</small></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Recent Transactions")
    recent = query("""
        SELECT
            id AS ID, tx_date AS Date, tx_type AS Type, amount AS Amount,
            wallet AS Wallet, from_wallet AS From_Wallet,
            to_wallet AS To_Wallet, person AS Person, category AS Category,
            note AS Note
        FROM transactions
        ORDER BY tx_date DESC, id DESC
        LIMIT 15
    """)
    if recent.empty:
        st.info("No transactions recorded yet.")
    else:
        st.dataframe(
            recent.style.format({"Amount": "₹{:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# ADD TRANSACTION
# =========================================================
elif page == "➕ Add Transaction":
    st.subheader("➕ Add Transaction")

    tx_type = st.selectbox(
        "Transaction Type",
        [
            "Opening Balance",
            "Income",
            "Expense",
            "Transfer",
            "Money Given",
            "Money Returned",
        ],
    )

    with st.form("transaction_form", clear_on_submit=True):
        d = st.date_input("Date", date.today())
        amount = st.number_input("Amount (₹)", min_value=0.01, step=100.0, format="%.2f")

        wallet = None
        from_wallet = None
        to_wallet = None
        person = ""
        category = ""

        if tx_type == "Transfer":
            from_wallet = st.selectbox("From", ["Cash", "UPI"])
            to_wallet = st.selectbox("To", ["UPI", "Cash"])
            if from_wallet == to_wallet:
                st.warning("From and To must be different.")
        elif tx_type in ["Opening Balance", "Income", "Expense", "Money Given", "Money Returned"]:
            wallet = st.selectbox("Wallet", ["Cash", "UPI"])

        if tx_type in ["Money Given", "Money Returned"]:
            existing_people = people()
            person_choice = st.selectbox(
                "Person",
                ["➕ New person"] + existing_people,
            )
            if person_choice == "➕ New person":
                person = st.text_input("Person Name *")
            else:
                person = person_choice

        if tx_type in ["Income", "Expense"]:
            category = st.text_input("Category", placeholder="Salary, food, shopping, etc.")

        note = st.text_area("Notes / Details")

        save = st.form_submit_button("💾 Save Transaction", type="primary")

    if save:
        if amount <= 0:
            st.error("Amount must be greater than zero.")
        elif tx_type == "Transfer" and from_wallet == to_wallet:
            st.error("From and To wallets must be different.")
        elif tx_type in ["Money Given", "Money Returned"] and not person.strip():
            st.error("Please enter a person name.")
        else:
            execute(
                """
                INSERT INTO transactions
                (tx_date, tx_type, amount, wallet, from_wallet, to_wallet,
                 person, category, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    d.isoformat(),
                    tx_type,
                    float(amount),
                    wallet,
                    from_wallet,
                    to_wallet,
                    person.strip(),
                    category.strip(),
                    note.strip(),
                    now(),
                ),
            )
            st.success(f"Saved {tx_type}: {money(amount)}")
            st.rerun()


# =========================================================
# PENDING MONEY
# =========================================================
elif page == "⏳ Pending Money":
    st.subheader("⏳ Pending Money Tracker")

    st.write(
        "Money given to other individuals is tracked here. "
        "It is separated from your available Cash and UPI balances."
    )

    p = pending_summary()

    if p.empty:
        st.info("No pending money records.")
    else:
        display = p.rename(
            columns={
                "person": "Person",
                "given": "Total Given",
                "returned": "Total Returned",
                "pending": "Pending",
            }
        )
        st.dataframe(
            display.style.format(
                {
                    "Total Given": "₹{:,.2f}",
                    "Total Returned": "₹{:,.2f}",
                    "Pending": "₹{:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Person Transaction Breakdown")
        person = st.selectbox("Select person", p["person"].tolist())
        detail = query("""
            SELECT
                id AS ID, tx_date AS Date, tx_type AS Type, amount AS Amount,
                wallet AS Wallet, note AS Notes
            FROM transactions
            WHERE person=?
            ORDER BY tx_date DESC, id DESC
        """, (person,))
        st.dataframe(
            detail.style.format({"Amount": "₹{:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# FIXED DEPOSITS (WITH MONTHLY INTEREST TO UPI)
# =========================================================
elif page == "🏦 Fixed Deposits":
    st.subheader("🏦 Fixed Deposits & Monthly UPI Payouts")
    st.caption("Creating an FD deducts the principal from your UPI balance. Monthly interest payouts deposit directly into your UPI wallet.")

    active = query("""
        SELECT
            id AS ID, start_date AS "Start Date", amount AS Amount,
            interest_rate AS "Interest %", maturity_date AS "Maturity Date",
            bank_name AS Bank, note AS Notes
        FROM fds
        WHERE status='Active'
        ORDER BY start_date DESC, id DESC
    """)

    if active.empty:
        st.info("No active Fixed Deposits found.")
    else:
        st.markdown("### Active Fixed Deposits")
        st.dataframe(
            active.style.format({
                "Amount": "₹{:,.2f}",
                "Interest %": "{:.2f}%"
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    col_create, col_payout = st.columns(2)

    with col_create:
        st.markdown("### ➕ Create New FD")
        with st.form("fd_form", clear_on_submit=True):
            fd_date = st.date_input("FD Start Date", date.today())
            fd_amount = st.number_input(
                "FD Principal Amount (₹)",
                min_value=0.01,
                step=1000.0,
                format="%.2f",
            )
            fd_rate = st.number_input(
                "Annual Interest Rate (%)",
                min_value=0.0,
                max_value=100.0,
                value=6.5,
                step=0.1,
            )
            fd_maturity = st.date_input("Maturity Date", date.today())
            bank = st.text_input("Bank / Institution Name")
            fd_note = st.text_area("FD Notes")
            create_fd = st.form_submit_button("🏦 Create FD from UPI", type="primary")

        if create_fd:
            if fd_amount > wallet_balance("UPI"):
                st.error(
                    f"Insufficient available UPI balance. Available UPI: {money(wallet_balance('UPI'))}"
                )
            elif fd_maturity < fd_date:
                st.error("Maturity date cannot precede start date.")
            else:
                execute(
                    """
                    INSERT INTO fds
                    (start_date, amount, interest_rate, maturity_date, bank_name,
                     note, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'Active', ?)
                    """,
                    (
                        fd_date.isoformat(),
                        float(fd_amount),
                        float(fd_rate),
                        fd_maturity.isoformat(),
                        bank.strip(),
                        fd_note.strip(),
                        now(),
                    ),
                )

                execute(
                    """
                    INSERT INTO transactions
                    (tx_date, tx_type, amount, wallet, category, note, created_at)
                    VALUES (?, 'FD Created', ?, 'UPI', 'FD', ?, ?)
                    """,
                    (
                        fd_date.isoformat(),
                        float(fd_amount),
                        f"FD created from UPI. {fd_note.strip()}".strip(),
                        now(),
                    ),
                )
                st.success(f"FD successfully created: {money(fd_amount)} deducted from UPI.")
                st.rerun()

    with col_payout:
        st.markdown("### 💸 Record Monthly Interest (to UPI)")
        active_ids = active["ID"].tolist() if not active.empty else []
        if active_ids:
            with st.form("interest_form", clear_on_submit=True):
                sel_fd_id = st.selectbox("Select Active FD ID", active_ids)
                payout_date = st.date_input("Interest Date", date.today())
                
                # Auto-calculate suggested monthly interest as a helpful default
                selected_row = active[active["ID"] == sel_fd_id].iloc[0]
                suggested_monthly_interest = round((selected_row["Amount"] * (selected_row["Interest %"] / 100)) / 12, 2)
                
                interest_amount = st.number_input(
                    "Monthly Interest Amount Received (₹)",
                    min_value=0.01,
                    value=float(suggested_monthly_interest),
                    step=10.0,
                    format="%.2f",
                )
                interest_note = st.text_input("Note (e.g., 'Monthly interest for May')", value="Monthly FD Interest")
                submit_interest = st.form_submit_button("📥 Credit Interest to UPI", type="primary")

            if submit_interest:
                execute(
                    """
                    INSERT INTO transactions
                    (tx_date, tx_type, amount, wallet, category, note, created_at)
                    VALUES (?, 'FD Interest Payout', ?, 'UPI', 'FD Interest', ?, ?)
                    """,
                    (
                        payout_date.isoformat(),
                        float(interest_amount),
                        f"FD #{sel_fd_id} monthly interest payout. {interest_note}".strip(),
                        now(),
                    ),
                )
                st.success(f"Successfully credited {money(interest_amount)} interest to your UPI wallet.")
                st.rerun()
        else:
            st.info("Create an active FD to log monthly interest payouts.")

    st.markdown("---")
    st.markdown("### ↩️ Mature / Close FD")
    if active_ids:
        with st.form("maturity_form"):
            fd_id = st.selectbox("Select FD ID to Close", active_ids, key="close_fd_select")
            selected = active[active["ID"] == fd_id].iloc[0]
            maturity_amount = st.number_input(
                "Total Principal Returned to UPI (₹)",
                min_value=0.01,
                value=float(selected["Amount"]),
                step=100.0,
                format="%.2f",
            )
            close_fd_btn = st.form_submit_button("↩️ Mature & Return Principal to UPI")

        if close_fd_btn:
            execute(
                "UPDATE fds SET status='Matured' WHERE id=?",
                (int(fd_id),),
            )
            execute(
                """
                INSERT INTO transactions
                (tx_date, tx_type, amount, wallet, category, note, created_at)
                VALUES (?, 'FD Matured', ?, 'UPI', 'FD', ?, ?)
                """,
                (
                    date.today().isoformat(),
                    float(maturity_amount),
                    f"FD #{fd_id} matured principal returned.",
                    now(),
                ),
            )
            st.success("FD marked as Matured and principal returned to UPI wallet.")
            st.rerun()


# =========================================================
# REPORTS
# =========================================================
elif page == "📊 Reports":
    st.subheader("📊 Financial Reports")

    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("From Date", date.today().replace(day=1))
    with c2:
        end = st.date_input("To Date", date.today())

    if start > end:
        st.error("From date must precede To date.")
    else:
        df = query("""
            SELECT
                id AS ID, tx_date AS Date, tx_type AS Type, amount AS Amount,
                wallet AS Wallet, from_wallet AS From_Wallet,
                to_wallet AS To_Wallet, person AS Person,
                category AS Category, note AS Notes
            FROM transactions
            WHERE tx_date BETWEEN ? AND ?
            ORDER BY tx_date, id
        """, (start.isoformat(), end.isoformat()))

        if df.empty:
            st.info("No transactions found in this date range.")
        else:
            st.dataframe(
                df.style.format({"Amount": "₹{:,.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("### Totals by Transaction Type")
            totals = df.groupby("Type", as_index=False)["Amount"].sum()
            st.dataframe(
                totals.style.format({"Amount": "₹{:,.2f}"}),
                use_container_width=True,
                hide_index=True,
            )


# =========================================================
# HISTORY / DELETE
# =========================================================
elif page == "📋 History":
    st.subheader("📋 Complete Transaction History")

    df = query("""
        SELECT
            id AS ID, tx_date AS Date, tx_type AS Type, amount AS Amount,
            wallet AS Wallet, from_wallet AS From_Wallet,
            to_wallet AS To_Wallet, person AS Person,
            category AS Category, due_date AS "Due Date", note AS Notes
        FROM transactions
        ORDER BY tx_date DESC, id DESC
    """)

    if df.empty:
        st.info("No transactions recorded yet.")
    else:
        st.dataframe(
            df.style.format({"Amount": "₹{:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.markdown("### Delete Transaction")

        tx_id = st.number_input("Transaction ID to Delete", min_value=1, step=1)

        if st.button("🗑️ Delete Transaction"):
            exists = query(
                "SELECT id FROM transactions WHERE id=?",
                (int(tx_id),),
            )
            if exists.empty:
                st.error("Transaction ID not found.")
            else:
                execute("DELETE FROM transactions WHERE id=?", (int(tx_id),))
                st.success(f"Transaction #{int(tx_id)} successfully deleted.")
                st.rerun()