import streamlit as st
import pandas as pd
import plotly.express as px
import json
from datetime import datetime

st.title("📈 Multi-Gas Line Chart – PPM Levels Over Time")

uploaded_files = st.file_uploader("Upload JSON Reports", type="json", accept_multiple_files=True)

if uploaded_files:
    gas_keys = [
        "Hydrogen (H2)", "Methane(CH4)", "Ethane(C2H6)", "Ethylene(C2H4)", "Acetylene(C2H2)",
        "Carbon Monoxide (CO)", "Carbon Dioxide(CO2)", "Oxygen (O2)", "Nitrogen (N2)"
    ]

    records = []

    for uploaded_file in uploaded_files:
        content = uploaded_file.read().decode("utf-8")
        data = json.loads(content)

        report_date = datetime.strptime(data["report_date"], "%Y-%m-%d")
        row = {
            "report_date": report_date,
            "transformer_id": data["transformer_id"],
            "substation_name": data["substation_name"]
        }

        for gas in gas_keys:
            val = data["parameters"].get(gas, "0")
            try:
                row[gas] = float(val) if val not in ["NT", "ND", ""] else 0.0
            except ValueError:
                row[gas] = 0.0
        records.append(row)

    # Create and prepare DataFrame
    df = pd.DataFrame(records)
    df.sort_values("report_date", inplace=True)

    # Convert wide to long format
    df_long = df.melt(
        id_vars=["report_date", "transformer_id", "substation_name"],
        value_vars=gas_keys,
        var_name="Gas Type",
        value_name="PPM Level"
    )

    # Plot multi-line graph
    fig = px.line(
        df_long,
        x="report_date",
        y="PPM Level",
        color="Gas Type",
        markers=True,
        title="Gas PPM Levels Over Time",
        hover_data=["transformer_id", "substation_name"]
    )

    fig.update_layout(
        xaxis_title="Report Date",
        yaxis_title="PPM Level",
        legend_title="Gas Type"
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Please upload at least one JSON report to begin.")
