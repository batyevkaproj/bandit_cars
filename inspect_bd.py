import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import requests
from io import BytesIO


# =============================
# CONFIG
# =============================
DB_PATH = "cars.db"
TABLE = "cars"
PAGE_SIZE = 24
# =============================


st.set_page_config(
    page_title="Bandit Cars",
    layout="wide"
)

st.title("🚗 Bandit Cars")
st.caption("OLX monitor — database viewer")


# =============================
# DB
# =============================
@st.cache_data
def load_data(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE}", conn)
    conn.close()
    return df


if not Path(DB_PATH).exists():
    st.error(f"DB file not found: {DB_PATH}")
    st.stop()

df = load_data(DB_PATH)

if df.empty:
    st.warning("Database is empty")
    st.stop()


# =============================
# SIDEBAR FILTERS
# =============================
st.sidebar.header("🔍 Filters")

q = st.sidebar.text_input("Search (title / location)", "").strip()

min_price, max_price = st.sidebar.slider(
    "Price (UAH)",
    min_value=int(df["price_uah"].fillna(0).min()),
    max_value=int(df["price_uah"].fillna(0).max()),
    value=(
        int(df["price_uah"].fillna(0).min()),
        int(df["price_uah"].fillna(0).max())
    )
)

sort = st.sidebar.selectbox(
    "Sort by",
    [
        "Newest",
        "Price ↑",
        "Price ↓"
    ]
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
    (view["price_uah"].fillna(0) >= min_price)
    & (view["price_uah"].fillna(0) <= max_price)
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
# GRID VIEW
# =============================
cols = st.columns(4)

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

        st.markdown(
            f"[Open OLX ad]({row.ad_url})",
            unsafe_allow_html=True
        )

        st.divider()


# =============================
# FOOTER
# =============================
st.caption(
    f"Showing {start + 1}-{min(end, total)} of {total} cars"
)
