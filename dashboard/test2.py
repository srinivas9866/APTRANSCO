from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
import psycopg2
import os
from datetime import datetime
from main import extract_sample_gas_data, build_query, generate_response
import json
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb
from langchain_chroma import Chroma


embeddings = HuggingFaceEmbeddings(
    model_name=r".\local_models\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
)
client = chromadb.HttpClient(host="10.96.76.161", port=8000)  # Update host if server is remote
vectorstore = Chroma(
    client=client,
    collection_name="dga_db",  # use same name as what was used when storing
    embedding_function=embeddings
)

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# PostgreSQL connection
conn = psycopg2.connect(
        host="10.96.76.161",        # or your DB server IP
        port="5432",             # default PostgreSQL port
        database="postgres",
        user="postgres",
        password="$$erver@&aps!"
)
cur = conn.cursor()

# --------------------------------------
# Utility Functions
# --------------------------------------

def get_substations():
    cur.execute('SELECT substation_short_id, substation_name FROM "DGA"."SUBSTATION_MASTER"')
    return {row[0]: row[1] for row in cur.fetchall()}

def get_transformers():
    cur.execute('SELECT ss_short_id, transformer_id, transformer_title, transformer_capacity_mva FROM "DGA"."SS-TRANSFORMER_MASTER"')
    transformer_map = {}
    for sid, tid, tname, cap in cur.fetchall():
        transformer_map.setdefault(sid, {})[tid] = {
            "transformer_name": tname,
            "transformer_capacity": cap
        }
    return transformer_map

def format_final_report(file_path, gas_data, form_data, response, reference_docs):
    lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"                      DGA DIAGNOSIS Report    {timestamp}\n")
    lines.append(f"Sample Name: {file_path}\n")
    lines.append("=" * 50)
    lines.append("Input:")
    for g in gas_data:
        lines.append(f"{g['Gas Name']} = {g['PPM']} ppm")
    for key, val in form_data.items():
        if key != 'title':
            pretty_key = key.replace('_', ' ').title()
            lines.append(f"{pretty_key} = {val}")
    lines.append("-" * 60)
    lines.append(response)
    lines.append("-" * 60)

    for i, ref in enumerate(reference_docs, 1):
        lines.append(f"Reference {i}")
        lines.append(f"source: {ref['source']}")
        lines.append("-" * 60)

    return "\n".join(lines)

# --------------------------------------
# Routes
# --------------------------------------

@app.route('/')
def index():
    substations = get_substations()
    transformer_map = get_transformers()
    return render_template('index.html', substations=substations, transformer_map=transformer_map)

@app.route('/process', methods=['POST'])
def process():
    file = request.files['pdf_file']
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # Step 1: Extract gas data
    gas_data = extract_sample_gas_data(file_path)

    # Step 2: Collect form data
    form_data = {
        "substation_id": request.form['substation_id'],
        "substation_name": request.form['substation_name'],
        "transformer_id": request.form['transformer_id'],
        "transformer_name": request.form['transformer_name'],
        "capacity": request.form['capacity'],
        "testing_date": request.form['testing_date'],
    }

    # Step 3: Generate AI query and response
    query = build_query(gas_data, form_data)
    response, reference_docs = generate_response(query)
    test_input_json = gas_data
    ai_reference_json = json.dumps(reference_docs, indent=2)
    ai_response = response

    # Step 4: Format report
    final_report = format_final_report(filename, gas_data, form_data, response, reference_docs)

    # Step 5: Save report as text file
    report_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'final_report.txt')
    with open(report_file_path, 'w') as f:
        f.write(final_report)

    # Step 6: Insert into PostgreSQL
    cur.execute('''
        INSERT INTO "DGA".dga_results
        (substation_id, transformer_id, testing_date, test_input_json, ai_response, ai_reference_json, report_pdf)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (
        form_data['substation_id'],
        form_data['transformer_id'],
        form_data['testing_date'],
        json.dumps(test_input_json),
        ai_response,
        ai_reference_json,
        final_report  # or save path to file
    ))
    conn.commit()

    return send_file(report_file_path, as_attachment=True)

# --------------------------------------
# Main
# --------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
