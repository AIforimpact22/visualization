import streamlit as st
import pandas as pd

from db_handler import DatabaseManager

st.set_page_config(page_title="Sales & Sales Items Browser", page_icon="🧾")
st.title("🧾 Sales & Sales Items Data Browser")

# ────────── Connect to DB ──────────
db = DatabaseManager()

# ────────── Load DataFrames ──────────
@st.cache_data(ttl=60*5, show_spinner=False)
def get_sales():
    return db.fetch_data("SELECT * FROM sales ORDER BY saleid DESC")

@st.cache_data(ttl=60*5, show_spinner=False)
def get_salesitems():
    return db.fetch_data("SELECT * FROM salesitem ORDER BY salesitemid DESC")

sales_df = get_sales()
salesitem_df = get_salesitems()

# ────────── UI Layout ──────────
tab1, tab2 = st.tabs(["Sales", "Sales Items"])

with tab1:
    st.subheader("Sales Table")
    if sales_df.empty:
        st.info("No sales records found.")
    else:
        st.dataframe(sales_df, use_container_width=True)
        # Optional: filters or search can be added here

with tab2:
    st.subheader("Sales Item Table")
    if salesitem_df.empty:
        st.info("No sales items found.")
    else:
        st.dataframe(salesitem_df, use_container_width=True)

# ────────── (Optional) Preview Uploaded CSVs ──────────
uploaded_sales = "/mnt/data/Sales.csv"
uploaded_salesitem = "/mnt/data/salesitem.csv"

with st.expander("Preview uploaded Sales.csv"):
    try:
        df = pd.read_csv(uploaded_sales)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not load Sales.csv: {e}")

with st.expander("Preview uploaded salesitem.csv"):
    try:
        df = pd.read_csv(uploaded_salesitem)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not load salesitem.csv: {e}")
