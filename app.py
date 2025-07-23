import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="Sales & Sales Items Browser", page_icon="🧾")
st.title("🧾 Sales & Sales Items Data Browser")

DB_FILE = "yourfile.db"   # update with your actual .db path

# --- Utility: List tables in the database
def list_tables(conn):
    query = "SELECT name FROM sqlite_master WHERE type='table'"
    return [row[0] for row in conn.execute(query)]

# --- Main load function
@st.cache_data(ttl=60*5)
def load_table(table):
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    return df

with sqlite3.connect(DB_FILE) as conn:
    tables = list_tables(conn)
st.write("**Available tables in database:**", tables)

# Adjust table names here if needed!
sales_table = "sales"
salesitem_table = "salesitems"  # with "s" as per your hint!

tab1, tab2 = st.tabs(["Sales", "Sales Items"])

with tab1:
    st.subheader(f"{sales_table} Table")
    try:
        df_sales = load_table(sales_table)
        st.dataframe(df_sales, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load table `{sales_table}`: {e}")

with tab2:
    st.subheader(f"{salesitem_table} Table")
    try:
        df_salesitem = load_table(salesitem_table)
        st.dataframe(df_salesitem, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load table `{salesitem_table}`: {e}")
