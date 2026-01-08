from flask import Flask, render_template, request, send_file, jsonify, redirect
import plotly.graph_objs as go
import psycopg2
import os
import pandas as pd
from io import BytesIO
import json

app = Flask(__name__)

# Function to connect to your PostgreSQL database
def get_db_connection():
    return psycopg2.connect(
    dbname="RAG",
    user="postgres",
    password="srinivas@123",
    host="localhost",
    port="5432"
)

#@app.route('/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def home():
    return redirect('/process')  # or render a homepage

@app.route('/trend/<transformer_id>')
def transformer_trend(transformer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    #cur.execute('SET search_path TO "DGA"')
    gas_keys = ["CO2", "Ethylene", "Acetylene", "Ethane", "H2", "O2", "N2", "Methane", "CO"]

    cur.execute("""
        SELECT 
            testing_date, 
            test_input_json
        FROM dga_results
        WHERE transformer_id = %s
        ORDER BY testing_date
    """, (transformer_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    if not rows:
        return jsonify({"html": "<p>No data available for trend.</p>"})

    # Build dataframe from extracted JSON
    dates = []
    gas_data = {key: [] for key in gas_keys}

    for date, raw_json in rows:
        try:
            json_data = json.loads(raw_json)
            gases = json_data["parameters"]["gases"]
        except Exception:
            continue

        dates.append(date)
        for gas in gas_keys:
            val = gases.get(gas, 0)
            try:
                val = float(val)
            except:
                val = 0.0  # Treat "Not Detected" or non-numeric as 0
            gas_data[gas].append(val)

    df = pd.DataFrame({"Date": dates, **gas_data})
    df["Date"] = pd.to_datetime(df["Date"])

    fig = go.Figure()
    for gas in gas_keys:
        fig.add_trace(go.Scatter(x=df["Date"], y=df[gas], mode='lines+markers', name=gas))

    fig.update_layout(
        title=f"Gas Trends for Transformer {transformer_id}",
        xaxis_title="Date",
        yaxis_title="PPM Level",
        legend_title="Gas Type",
        height=500
    )

    return jsonify({"html": fig.to_html(full_html=False)})





@app.route('/show/<int:report_id>')
def show_report(report_id):
    conn = get_db_connection()
    cur = conn.cursor()
    #cur.execute('SET search_path TO "DGA"')
    # Fetch the PDF bytes from BYTEA column using object_id
    print(report_id)
    cur.execute("SELECT report_pdf FROM dga_results WHERE object_id = %s", (report_id,))
    row = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if row and row[0]:
        pdf_data = row[0]
        return send_file(
            BytesIO(pdf_data),
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'report_{report_id}.pdf'
        )
    else:
        return "Report not found", 404

    
@app.route('/process', methods=['GET', 'POST'])
def test_report():
    conn = get_db_connection()
    cur = conn.cursor()
    #cur.execute('SET search_path TO "DGA"')
    # Fetch substation IDs and names for dropdown
    cur.execute("SELECT substation_short_id, substation_name FROM substation_master")
    substations = {row[0]: row[1] for row in cur.fetchall()}

    results = []
    success = False

    if request.method == 'POST':
        selected_id = request.form.get('substation_short_id')

        if selected_id:
            cur.execute("""
                SELECT 
                    object_id,
                    transformer_id, 
                    testing_date, 
                    test_input_json::json->'parameters'->'gases'->>'CO2',
                    test_input_json::json->'parameters'->'gases'->>'Ethylene',
                    test_input_json::json->'parameters'->'gases'->>'Acetylene',
                    test_input_json::json->'parameters'->'gases'->>'Ethane',
                    test_input_json::json->'parameters'->'gases'->>'H2',
                    test_input_json::json->'parameters'->'gases'->>'O2',
                    test_input_json::json->'parameters'->'gases'->>'N2',
                    test_input_json::json->'parameters'->'gases'->>'Methane',
                    test_input_json::json->'parameters'->'gases'->>'CO',
                    test_input_json::json->'parameters'->>'capacity',
                    report_pdf
                FROM dga_results
                WHERE substation_id = %s
                ORDER BY testing_date DESC
            """, (selected_id,))
            rows = cur.fetchall()

            for row in rows:
                results.append({
                        'report_id': row[0],              # object_id
                        'transformer_id': row[1],
                        'testing_date': row[2],
                        'CO2': row[3],
                        'Ethylene': row[4],
                        'Acetylene': row[5],
                        'Ethane': row[6],
                        'H2': row[7],
                        'O2': row[8],
                        'N2': row[9],
                        'Methane': row[10],
                        'CO': row[11],
                        'capacity': row[12],
                        'substation_name': substations.get(selected_id, "N/A")
                })
            success = True

    cur.close()
    conn.close()

    return render_template("test_reports.html", substations=substations, results=results, success=success)

if __name__ == '__main__':
    app.run(host='192.168.1.3', port=5000, debug=True)

