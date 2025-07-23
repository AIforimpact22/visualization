import streamlit as st
import pandas as pd
import time
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

st.set_page_config(page_title="Realtime Sales D3 Chart", page_icon="📈")
st.title("📈 Realtime Sales D3 Chart")

REFRESH = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 5)
NUM_SALES = st.sidebar.slider("Number of Recent Sales to Show", 5, 50, 10)

db = DatabaseManager()

@st.cache_data(ttl=2)
def get_recent_sales(n=10):
    return db.fetch_data(
        f"SELECT saleid, saletime, totalamount FROM sales ORDER BY saleid DESC LIMIT {n}"
    )

@st.cache_data(ttl=2)
def get_salesitems_for_sale(saleid):
    return db.fetch_data(
        "SELECT itemid, quantity, unitprice, totalprice FROM salesitems WHERE saleid = %s ORDER BY salesitemid", (saleid,)
    )

placeholder = st.empty()
while True:
    with placeholder.container():
        st.write("Last refreshed at", time.strftime("%H:%M:%S"))

        sales_df = get_recent_sales(NUM_SALES)
        if sales_df.empty:
            st.info("No sales yet.")
            time.sleep(REFRESH)
            continue

        sales_df = sales_df.sort_values("saleid")
        sales_df['saletime'] = pd.to_datetime(sales_df['saletime'])
        chart_data = [
            {
                "date": d.strftime("%Y-%m-%dT%H:%M:%S"),
                "totalamount": float(v)
            }
            for d, v in zip(sales_df['saletime'], sales_df['totalamount'])
        ]
        chart_json = json.dumps(chart_data)

        d3_code = f"""
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <div id="chart"></div>
        <script>
        const sales = {chart_json};
        const width = 928, height = 400;
        const marginTop = 20, marginRight = 30, marginBottom = 30, marginLeft = 60;

        sales.forEach(d => d.date = new Date(d.date));

        const x = d3.scaleUtc(
            d3.extent(sales, d => d.date),
            [marginLeft, width - marginRight]
        );
        const y = d3.scaleLinear(
            [0, d3.max(sales, d => d.totalamount)],
            [height - marginBottom, marginTop]
        );
        const line = d3.line()
            .x(d => x(d.date))
            .y(d => y(d.totalamount));

        const svg = d3.select("#chart").append("svg")
            .attr("width", width)
            .attr("height", height)
            .attr("viewBox", [0, 0, width, height])
            .attr("style", "max-width: 100%; height: auto; height: intrinsic; background: #fff; border-radius: 12px;");

        svg.append("g")
            .attr("transform", `translate(0,${height - marginBottom})`)
            .call(d3.axisBottom(x).ticks(width / 100).tickSizeOuter(0));

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

        svg.append("path")
            .attr("fill", "none")
            .attr("stroke", "steelblue")
            .attr("stroke-width", 2)
            .attr("d", line(sales));
        </script>
        """

        components.html(d3_code, height=420)

        # Select and plot items for a sale (with unique key)
        saleids = sales_df['saleid'].tolist()[::-1]
        selected = st.selectbox("Show items for Sale ID:", saleids, key="saleid_select")
        items_df = get_salesitems_for_sale(selected)
        st.subheader(f"Item Quantities for Sale {selected}")

        if items_df.empty:
            st.info("No items for this sale.")
        else:
            chart_df = items_df.groupby("itemid", as_index=False)["quantity"].sum()
            st.bar_chart(
                data=chart_df,
                x="itemid",
                y="quantity",
                use_container_width=True
            )

    time.sleep(REFRESH)
    st.cache_data.clear()
