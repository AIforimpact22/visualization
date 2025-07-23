import streamlit as st
import pandas as pd
import json
import datetime as dt
from db_handler import DatabaseManager
import streamlit.components.v1 as components

# optional autorefresh
try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# ────────────────── Page config ──────────────────
st.set_page_config(page_title="Family / Section Visuals", page_icon="🗃️")
st.title("🗃️ Family / Section / Department / Class Visualisations")

# ────────── Sidebar controls (Realtime tab) ──────────
REFRESH  = st.sidebar.slider("Realtime refresh (seconds)", 2, 30, 5)
NUM_SALE = st.sidebar.slider("Analyse last # sales", 5, 100, 30)
TOP_N    = st.sidebar.slider("Show top N groups", 5, 30, 10)

# Mapping of DB columns → friendly label
GROUP_COLS = [
    ("familycat",     "Family"),
    ("sectioncat",    "Section"),
    ("departmentcat", "Department"),
    ("classcat",      "Class"),
]

tab1, tab2 = st.tabs(["Catalog Structure", "Realtime Sales"])

db = DatabaseManager()

# ────────────────── TAB 1 – catalog counts ──────────────────
with tab1:
    st.subheader("Catalogue distribution (from `item` table)")

    @st.cache_data(ttl=600)
    def get_item_counts():
        return db.fetch_data(
            "SELECT familycat, sectioncat, departmentcat, classcat FROM item"
        )

    items_df = get_item_counts()

    for col, label in GROUP_COLS:
        # Build small DF of counts
        counts = (
            items_df[col]
            .fillna("Unknown")
            .replace("", "Unknown")
            .value_counts()
            .reset_index()
            .rename(columns={"index": label, col: "Count"})
        )

        # Chart height proportional to #categories
        chart_height = max(180, 100 + len(counts) * 18)

        # JSON for D3
        chart_data = [
            {"group": str(row[label]), "count": int(row["Count"])}
            for _, row in counts.iterrows()
        ][:30]                                # keep first 30 groups
        chart_json = json.dumps(chart_data)

        # ---------- D3 code (all JS braces escaped) ----------
        d3_code = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="{col}_chart"></div>
<script>
const data = {chart_json};
const width = 650;
const height = {chart_height};
const margin = {{top:40, right:20, bottom:30, left:120}};

// Scales
const y = d3.scaleBand()
    .domain(data.map(d => d.group))
    .rangeRound([margin.top, height - margin.bottom])
    .padding(0.14);

const x = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.count) * 1.05]).nice()
    .range([margin.left, width - margin.right]);

const color = d3.scaleOrdinal(d3.schemeSet2);

// SVG
const svg = d3.select("#{col}_chart").append("svg")
    .attr("width",  width)
    .attr("height", height)
    .attr("viewBox", [0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#f8fafc;border-radius:12px;");

// Bars
svg.append("g")
  .selectAll("rect")
  .data(data)
  .join("rect")
    .attr("x", x(0))
    .attr("y", d => y(d.group))
    .attr("width", d => x(d.count)-x(0))
    .attr("height", y.bandwidth())
    .attr("rx",7)
    .attr("fill",(d,i)=>color(i));

// Axes
svg.append("g")
  .attr("transform", `translate(0,${{margin.top}})`)
  .call(d3.axisTop(x).ticks(width/120,"s"))
  .call(g => g.select(".domain").remove());

svg.append("g")
  .attr("transform", `translate(${{margin.left}},0)`)
  .call(d3.axisLeft(y).tickSize(0))
  .call(g => g.select(".domain").remove());

// Labels
svg.selectAll("text.value")
  .data(data)
  .join("text")
    .attr("x", d => x(d.count)+8)
    .attr("y", d => y(d.group)+y.bandwidth()/2+3)
    .text(d => d3.format(",")(d.count))
    .attr("fill","#1e293b")
    .attr("font-size","1.05rem");
</script>
"""
        components.html(d3_code, height=chart_height + 40)

# ────────────────── TAB 2 – realtime sales ──────────────────
with tab2:
    GROUP_KEY, GROUP_LABEL = st.selectbox(
        "Group realtime sales by:",
        GROUP_COLS,
        format_func=lambda x: x[1],
        index=0
    )

    # optional autorefresh
    if st_autorefresh:
        st_autorefresh(interval=REFRESH * 1000, key="family_refresh")

    @st.cache_data(ttl=2)  # refresh every 2 s when called
    def fetch_realtime_blocks(n_sales: int):
        # 1. Latest saleids
        sales = db.fetch_data(
            "SELECT saleid, saletime FROM sales ORDER BY saleid DESC LIMIT %s",
            (n_sales,)
        )
        if sales.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # 2. Related salesitems
        saleids = tuple(sales["saleid"])
        salesitems = db.fetch_data(
            f"SELECT saleid, itemid, quantity, totalprice "
            f"FROM salesitems WHERE saleid IN %s", (saleids,)
        )

        if salesitems.empty:
            return sales, salesitems, pd.DataFrame()

        # 3. Needed item meta
        itemids = tuple(salesitems["itemid"].unique())
        items = db.fetch_data(
            f"""
            SELECT itemid, familycat, sectioncat, departmentcat, classcat
            FROM item WHERE itemid IN %s
            """,
            (itemids,)
        )
        return sales, salesitems, items

    sales, salesitems, items = fetch_realtime_blocks(NUM_SALE)

    if sales.empty or salesitems.empty or items.empty:
        st.info("No recent sales data.")
        st.stop()

    # Merge
    merged = (
        salesitems
        .merge(items, on="itemid", how="left")
        .merge(sales[["saleid", "saletime"]], on="saleid", how="left")
    )
    merged[GROUP_KEY] = merged[GROUP_KEY].fillna("Unknown").replace("", "Unknown")

    agg = (
        merged.groupby(GROUP_KEY, dropna=False)
        .agg(total_sales=("totalprice", "sum"))
        .sort_values("total_sales", ascending=False)
        .head(TOP_N)
        .reset_index()
    )

    if agg.empty:
        st.info("No grouped sales to display.")
    else:
        realtime_json = json.dumps([
            {"group": str(r[GROUP_KEY]), "total_sales": float(r["total_sales"])}
            for _, r in agg.iterrows()
        ])

        d3_rt = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="rt_chart"></div>
<script>
const data = {realtime_json};
const width = 850, height = 420;
const margin = {{top:40,right:40,bottom:60,left:120}};
const svg = d3.select("#rt_chart").append("svg")
    .attr("width",width).attr("height",height)
    .attr("viewBox",[0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#fff;border-radius:14px;");

const y = d3.scaleBand()
    .domain(data.map(d=>d.group))
    .rangeRound([margin.top,height-margin.bottom])
    .padding(0.12);

const x = d3.scaleLinear()
    .domain([0,d3.max(data,d=>d.total_sales)*1.05]).nice()
    .range([margin.left,width-margin.right]);

const color = d3.scaleOrdinal(d3.schemeSet2);

svg.append("g")
  .selectAll("rect")
  .data(data)
  .join("rect")
    .attr("x",x(0))
    .attr("y",d=>y(d.group))
    .attr("width",d=>x(d.total_sales)-x(0))
    .attr("height",y.bandwidth())
    .attr("rx",7)
    .attr("fill",(d,i)=>color(i));

svg.append("g")
  .attr("transform",`translate(0,${{margin.top}})`)
  .call(d3.axisTop(x).ticks(width/120,"s"))
  .call(g=>g.select(".domain").remove());

svg.append("g")
  .attr("transform",`translate(${{margin.left}},0)`)
  .call(d3.axisLeft(y).tickSize(0))
  .call(g=>g.select(".domain").remove());

svg.selectAll("text.value")
  .data(data)
  .join("text")
    .attr("x",d=>x(d.total_sales)+8)
    .attr("y",d=>y(d.group)+y.bandwidth()/2+3)
    .text(d=>d3.format(",.0f")(d.total_sales))
    .attr("fill","#1e293b")
    .attr("font-size","1.1rem");
</script>
"""
        st.write(f"### Top {TOP_N} {GROUP_LABEL}s – last {NUM_SALE} sales")
        components.html(d3_rt, height=450)
