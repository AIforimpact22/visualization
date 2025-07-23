import streamlit as st
import pandas as pd
import time
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(page_title="Cashier Sales Visualization", page_icon="🧑‍💼")
st.title("🧑‍💼 Cashier Sales Visualization")

REFRESH = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 5)
NUM_SALES = st.sidebar.slider("Number of Recent Sales to Show", 5, 100, 30)

if st_autorefresh:
    st_autorefresh(interval=REFRESH * 1000, key="cashier_refresh")

db = DatabaseManager()

@st.cache_data(ttl=2)
def get_recent_sales(n=30):
    return db.fetch_data(
        f"SELECT saleid, saletime, totalamount, cashier FROM sales ORDER BY saleid DESC LIMIT {n}"
    )

st.write("Last refreshed at", time.strftime("%H:%M:%S"))

sales_df = get_recent_sales(NUM_SALES)
if sales_df.empty:
    st.info("No sales yet.")
    st.stop()

sales_df = sales_df.sort_values("saletime")
sales_df['saletime'] = pd.to_datetime(sales_df['saletime'])

# Group by cashier
chart_data = []
for cashier, group in sales_df.groupby("cashier"):
    for i, row in group.iterrows():
        chart_data.append({
            "date": row['saletime'].strftime("%Y-%m-%dT%H:%M:%S"),
            "value": float(row['totalamount']),
            "cashier": cashier
        })

chart_json = json.dumps(chart_data)

# D3 multi-line chart (one line per cashier, animated, styled)
d3_code = """
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="chart"></div>
<script>
const data = """ + chart_json + """;

// Parse dates
data.forEach(d => d.date = new Date(d.date));

// Group data by cashier
const dataByCashier = Array.from(d3.group(data, d => d.cashier), ([key, values]) => ({key, values}));

const width = 928;
const height = 600;
const marginTop = 20;
const marginRight = 30;
const marginBottom = 30;
const marginLeft = 60;

// Scales
const x = d3.scaleUtc(
    d3.extent(data, d => d.date),
    [marginLeft, width - marginRight]
);
const y = d3.scaleLinear(
    [0, d3.max(data, d => d.value)],
    [height - marginBottom, marginTop]
);
const z = d3.scaleOrdinal(d3.schemeCategory10);

// Line generator
const line = d3.line()
    .defined(d => !isNaN(d.value))
    .x(d => x(d.date))
    .y(d => y(d.value));

// SVG container
const svg = d3.select("#chart").append("svg")
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", [0, 0, width, height])
    .attr("style", "max-width: 100%; height: auto; background: #fff; border-radius: 12px;");

// X-axis
svg.append("g")
    .attr("transform", `translate(0,${height - marginBottom})`)
    .call(d3.axisBottom(x).ticks(width / 100).tickSizeOuter(0));

// Y-axis + grid
svg.append("g")
    .attr("transform", `translate(${marginLeft},0)`)
    .call(d3.axisLeft(y).ticks(height / 40))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll(".tick line").clone()
        .attr("x2", width - marginLeft - marginRight)
        .attr("stroke-opacity", 0.1))
    .call(g => g.append("text")
        .attr("x", -marginLeft + 5)
        .attr("y", 10)
        .attr("fill", "currentColor")
        .attr("text-anchor", "start")
        .text("↑ Sale Amount"));

// Animate and draw lines for each cashier
const g = svg.append("g")
    .attr("font-family", "sans-serif")
    .attr("font-size", 12)
    .attr("fill", "none")
    .attr("stroke-width", 2);

dataByCashier.forEach((series, i) => {
    g.append("path")
        .datum(series.values)
        .attr("d", line)
        .attr("stroke", z(series.key))
        .attr("id", "line-" + i);

    // Label at the end of each line
    const last = series.values[series.values.length - 1];
    if (last) {
        g.append("text")
            .attr("paint-order", "stroke")
            .attr("stroke", "#fff")
            .attr("stroke-width", 4)
            .attr("fill", z(series.key))
            .attr("dx", 8)
            .attr("dy", "0.32em")
            .attr("x", x(last.date))
            .attr("y", y(last.value))
            .text(series.key);
    }
});
</script>
"""

components.html(d3_code, height=650)
