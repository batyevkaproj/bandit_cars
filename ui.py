import sqlite3
from pathlib import Path
from io import BytesIO

import pandas as pd
import streamlit as st
import requests


# =============================
# AUTO DB DISCOVERY
# =============================
BASE_DIR = Path(__file__).parent.resolve()

def find_db_with_cars(base: Path) -> Path | None:
    for db in base.rglob("*.db"):
        try:
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            tables = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            conn.close()
            if ("cars",) in tables:
                return db
        except Exception:
            pass
    return None


DB_PATH = find_db_with_cars(BASE_DIR)
TABLE = "cars"

if DB_PATH is None:
    st.error("❌ SQLite DB with table `cars` not found")
    st.stop()


# =============================
# STREAMLIT CONFIG
# =============================
st.set_page_config(
    page_title="Bandit Cars",
    layout="wide"
)

st.title("🚗 Bandit Cars")
st.caption(f"DB: {DB_PATH}")


# =============================
# LOAD DATA
# =============================
@st.cache_data
def load_data(db_path: Path) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE}", conn)
    conn.close()
    return df


df = load_data(DB_PATH)

if df.empty:
    st.warning("Database is empty")
    st.stop()


# =============================
# SIDEBAR FILTERS
# =============================
st.sidebar.header("🔍 Filters")

q = st.sidebar.text_input("Search (title / location)", "").strip()

price_min = int(df["price_uah"].fillna(0).min())
price_max = int(df["price_uah"].fillna(0).max())

price_range = st.sidebar.slider(
    "Price (UAH)",
    min_value=price_min,
    max_value=price_max,
    value=(price_min, price_max)
)

sort = st.sidebar.selectbox(
    "Sort",
    ["Newest", "Price ↑", "Price ↓"]
)


# =============================
# FILTER LOGIC
# =============================
view = df.copy()

if q:
    view = view[
        view["title"].str.contains(q, case=False, na=False)
        | view["location"].str.contains(q, case=False, na=False)
    ]

view = view[
    (view["price_uah"].fillna(0) >= price_range[0])
    & (view["price_uah"].fillna(0) <= price_range[1])
]

if sort == "Newest":
    view = view.sort_values("created_at", ascending=False)
elif sort == "Price ↑":
    view = view.sort_values("price_uah", ascending=True)
elif sort == "Price ↓":
    view = view.sort_values("price_uah", ascending=False)


# =============================
# PAGINATION
# =============================
PAGE_SIZE = 24
total = len(view)
pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

page = st.number_input(
    "Page",
    min_value=1,
    max_value=pages,
    value=1,
    step=1
)

start = (page - 1) * PAGE_SIZE
end = start + PAGE_SIZE
page_df = view.iloc[start:end]


# =============================
# IMAGE RENDER
# =============================
def render_image(url: str):
    if not url:
        st.image("https://via.placeholder.com/400x300?text=No+Image")
        return
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        st.image(BytesIO(r.content), use_container_width=True)
    except Exception:
        st.image("https://via.placeholder.com/400x300?text=Image+Error")


# =============================
# GRID VIEW
# =============================
cols = st.columns(4)

for i, row in enumerate(page_df.itertuples()):
    with cols[i % 4]:
        render_image(row.image_url)

        st.markdown(
            f"**{row.title[:80]}{'…' if len(row.title) > 80 else ''}**"
        )

        if row.price_uah:
            st.markdown(f"💰 **{row.price_uah:,} UAH**")
        else:
            st.markdown("💰 —")

        if row.location:
            st.caption(f"📍 {row.location}")

        st.markdown(f"[Open OLX ad]({row.ad_url})")
        st.divider()


st.caption(
    f"Showing {start + 1}-{min(end, total)} of {total}"
)
