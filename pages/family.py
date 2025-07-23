import streamlit as st
import pandas as pd
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

# ─── optional auto‑refresh helper ───
try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# ─── page config ───
st.set_page_config(page_title="Family / Section Visuals", page_icon="🗃️")
st.title("🗃️ Family / Section / Department / Class Visualisations")

REFRESH  = st.sidebar.slider("Realtime refresh (s)", 2, 30, 5)
NUM_SALE = st.sidebar.slider("Analyse last # sales", 5, 100, 30)
TOP_N    = st.sidebar.slider("Show top N groups", 5, 30, 10)

GROUP_COLS = [
    ("familycat",     "Family"),
    ("sectioncat",    "Section"),
    ("departmentcat", "Department"),
    ("classcat",      "Class"),
]

tab1, tab2 = st.tabs(["Catalog Structure", "Realtime Sales"])
db = DatabaseManager()

# ───────────────────────── TAB 1 ─────────────────────────
with tab1:
    st.subheader("Catalogue distribution (item table)")

    @st.cache_data(ttl=600)
    def fetch_item_cats():
        return db.fetch_data(
            "SELECT familycat, sectioncat, departmentcat, classcat FROM item"
        )

    items_df = fetch_item_cats()

    for col, label in GROUP_COLS:
        st.markdown(f"#### {label}s")
        counts = (
            items_df[col]
            .fillna("Unknown")
            .replace("", "Unknown")
            .value_counts()
            .reset_index()
            .rename(columns={"index": label, col: "Count"})
        )

        chart_data = [
            {"group": str(row[0]), "count": int(row[1])}
            for row in counts.itertuples(index=False, name=None)
        ][:30]
        chart_json   = json.dumps(chart_data)
        chart_height = max(180, 100 + len(chart_data) * 18)

        d3_code = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="{col}_chart"></div>
<script>
const data = {chart_json};
const width=650,height={chart_height},margin={{top:40,right:20,bottom:30,left:120}};
const y=d3.scaleBand().domain(data.map(d=>d.group))
    .rangeRound([margin.top,height-margin.bottom]).padding(0.14);
const x=d3.scaleLinear()
    .domain([0,d3.max(data,d=>d.count)*1.05]).nice()
    .range([margin.left,width-margin.right]);
const color=d3.scaleOrdinal(d3.schemeSet2);
const svg=d3.select("#{col}_chart").append("svg")
    .attr("width",width).attr("height",height)
    .attr("viewBox",[0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#f8fafc;border-radius:12px;");
svg.append("g").selectAll("rect").data(data).join("rect")
    .attr("x",x(0)).attr("y",d=>y(d.group))
    .attr("width",d=>x(d.count)-x(0)).attr("height",y.bandwidth())
    .attr("rx",7).attr("fill",(d,i)=>color(i));
svg.append("g")
    .attr("transform",`translate(0,${{margin.top}})`)
    .call(d3.axisTop(x).ticks(width/120,"s"))
    .call(g=>g.select(".domain").remove());
svg.append("g")
    .attr("transform",`translate(${{margin.left}},0)`)
    .call(d3.axisLeft(y).tickSize(0))
    .call(g=>g.select(".domain").remove());
svg.selectAll("text.val").data(data).join("text")
    .attr("x",d=>x(d.count)+8).attr("y",d=>y(d.group)+y.bandwidth()/2+3)
    .text(d=>d3.format(",")(d.count))
    .attr("fill","#1e293b").attr("font-size","1.05rem");
</script>
"""
        components.html(d3_code, height=chart_height + 40)

# ───────────────────────── TAB 2 ─────────────────────────
with tab2:
    sel_col, sel_label = st.selectbox(
        "Group realtime sales by:", GROUP_COLS, format_func=lambda x: x[1]
    )
    if st_autorefresh:
        st_autorefresh(interval=REFRESH * 1000, key="family_rt_refresh")

    @st.cache_data(ttl=2)
    def fetch_blocks(n_sales: int):
        sales = db.fetch_data(
            "SELECT saleid, saletime FROM sales ORDER BY saleid DESC LIMIT %s",
            (n_sales,)
        )
        if sales.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        saleids = tuple(int(x) for x in sales.saleid.tolist())  # ← cast to int
        placeholders = ",".join(["%s"] * len(saleids))

        salesitems = db.fetch_data(
            f"SELECT saleid, itemid, quantity, totalprice "
            f"FROM salesitems WHERE saleid IN ({placeholders})",
            saleids,
        )
        if salesitems.empty:
            return sales, salesitems, pd.DataFrame()

        itemids = tuple(int(x) for x in salesitems.itemid.unique())  # ← cast
        placeholders = ",".join(["%s"] * len(itemids))
        items = db.fetch_data(
            f"""SELECT itemid,familycat,sectioncat,
                       departmentcat,classcat
                 FROM item WHERE itemid IN ({placeholders})""",
            itemids,
        )
        return sales, salesitems, items

    sales, salesitems, items = fetch_blocks(NUM_SALE)
    if sales.empty or salesitems.empty or items.empty:
        st.info("No recent sales data.")
        st.stop()

    merged = (
        salesitems.merge(items, on="itemid", how="left")
                  .merge(sales[["saleid", "saletime"]], on="saleid", how="left")
    )
    merged[sel_col] = merged[sel_col].fillna("Unknown").replace("", "Unknown")

    top_groups = (
        merged.groupby(sel_col, dropna=False)["totalprice"]
              .sum()
              .sort_values(ascending=False)
              .head(TOP_N)
              .reset_index()
    )

    if top_groups.empty:
        st.info("No grouped sales to display.")
    else:
        rt_json = json.dumps([
            {"group": str(r[sel_col]), "total_sales": float(r.totalprice)}
            for _, r in top_groups.iterrows()
        ])
        d3_rt = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="rt_chart"></div>
<script>
const data={rt_json};
const width=850,height=420,margin={{top:40,right:40,bottom:60,left:120}};
const y=d3.scaleBand().domain(data.map(d=>d.group))
    .rangeRound([margin.top,height-margin.bottom]).padding(0.12);
const x=d3.scaleLinear()
    .domain([0,d3.max(data,d=>d.total_sales)*1.05]).nice()
    .range([margin.left,width-margin.right]);
const color=d3.scaleOrdinal(d3.schemeSet2);
const svg=d3.select("#rt_chart").append("svg")
    .attr("width",width).attr("height",height)
    .attr("viewBox",[0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#fff;border-radius:14px;");
svg.append("g").selectAll("rect").data(data).join("rect")
    .attr("x",x(0)).attr("y",d=>y(d.group))
    .attr("width",d=>x(d.total_sales)-x(0))
    .attr("height",y.bandwidth()).attr("rx",7)
    .attr("fill",(d,i)=>color(i));
svg.append("g")
    .attr("transform",`translate(0,${{margin.top}})`)
    .call(d3.axisTop(x).ticks(width/120,"s"))
    .call(g=>g.select(".domain").remove());
svg.append("g")
    .attr("transform",`translate(${{margin.left}},0)`)
    .call(d3.axisLeft(y).tickSize(0))
    .call(g=>g.select(".domain").remove());
svg.selectAll("text.val").data(data).join("text")
    .attr("x",d=>x(d.total_sales)+8)
    .attr("y",d=>y(d.group)+y.bandwidth()/2+3)
    .text(d=>d3.format(",.0f")(d.total_sales))
    .attr("fill","#1e293b").attr("font-size","1.1rem");
</script>
"""
        st.write(f"### Top {TOP_N} {sel_label}s — last {NUM_SALE} sales")
        components.html(d3_rt, height=450)
