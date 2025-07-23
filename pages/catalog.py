# ------------------ Catalog Structure ------------------
# Shows static bar‑charts for Family / Section / Department / Class
# --------------------------------------------------------
import streamlit as st
import pandas as pd
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

st.set_page_config(page_title="Catalog Structure", page_icon="📚")
st.title("📚 Catalog Structure (Item Table)")

db = DatabaseManager()

@st.cache_data(ttl=600)
def fetch_item_cats():
    return db.fetch_data(
        "SELECT familycat, sectioncat, departmentcat, classcat FROM item"
    )

GROUP_COLS = [
    ("familycat",     "Family"),
    ("sectioncat",    "Section"),
    ("departmentcat", "Department"),
    ("classcat",      "Class"),
]

items_df = fetch_item_cats()

for col, label in GROUP_COLS:
    st.markdown(f"#### {label}s")
    counts = (
        items_df[col].fillna("Unknown").replace("", "Unknown")
        .value_counts().reset_index()
        .rename(columns={"index": label, col: "Count"})
    )
    chart_data = [{"group": str(r[0]), "count": int(r[1])}
                  for r in counts.itertuples(index=False, name=None)][:30]
    chart_json   = json.dumps(chart_data)
    chart_height = max(180, 100 + len(chart_data) * 18)

    # ---------- D3 horizontal bar chart ----------
    d3_code = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="{col}_chart"></div>
<script>
const data={chart_json};
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
    .attr("x",d=>x(d.count)+8)
    .attr("y",d=>y(d.group)+y.bandwidth()/2+3)
    .text(d=>d3.format(",")(d.count))
    .attr("fill","#1e293b").attr("font-size","1.05rem");
</script>
"""
    components.html(d3_code, height=chart_height + 40)
