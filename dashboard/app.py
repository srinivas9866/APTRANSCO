from flask import Flask, render_template, request, session, send_file, url_for,redirect
from pathlib import Path
from main import extract_sample_gas_data, build_query, generate_response
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from werkzeug.utils import secure_filename
from textwrap import wrap
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
#import secrets
import os
import psycopg2
import json
#from langchain.vectorstores import Chroma
import chromadb
#from langchain_community.vectorstores import Chroma

app = Flask(__name__)
app.secret_key = "Srinivas@143"

UPLOAD_FOLDER = "uploads"
DOCS_FOLDER = "static/docs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOCS_FOLDER, exist_ok=True)

# Load vector store
embeddings = HuggingFaceEmbeddings(
    model_name=r".\local_models\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
)
'''
vectorstore = Chroma(persist_directory="./dga_db", embedding_function=embeddings)
'''
client = chromadb.HttpClient(host="10.96.76.161", port=8000)  # Update host if server is remote
vectorstore = Chroma(
    client=client,
    collection_name="dga_db",  # use same name as what was used when storing
    embedding_function=embeddings
)

# Connect to PostgreSQL
'''

conn = psycopg2.connect(
    dbname="RAG",
    user="postgres",
    password="srinivas@123",
    host="localhost",
    port="5432"
)
'''
conn = psycopg2.connect(
        host="10.96.76.161",        # or your DB server IP
        port="5432",             # default PostgreSQL port
        database="postgres",
        user="postgres",
        password="$$erver@&aps!"
)

cur = conn.cursor()
#cur.execute('SET search_path TO "DGA"')

@app.route("/", methods=["GET"])
def index():
    cur.execute("SELECT substation_short_id, substation_name FROM substation_master")
    substations = {row[0]: row[1] for row in cur.fetchall()}


    cur.execute("SELECT substation_short_id, transformer_id, transformer_name, transformer_capacity FROM transformer_master")
    transformer_map = {}
    for sid, tid, tname, cap in cur.fetchall():
        if sid not in transformer_map:
            transformer_map[sid] = {}
        transformer_map[sid][tid] = {
            "transformer_name": tname,
            "transformer_capacity": cap
        }
    
    return render_template("index.html", form_data={}, substations=substations, transformers=transformer_map)



@app.route("/download", methods=["GET"])
def download():
    report_text = session.get("final_report", "")
    file_name = session.get("upload_name", "report.pdf")

    if not report_text:
        return "No report available to download."

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    lines = report_text.split("\n")
    y = height - 40
    for line in lines:
        wrapped = wrap(line, width=100)
        for part in wrapped:
            p.drawString(40, y, part)
            y -= 15
            if y < 40:
                p.showPage()
                y = height - 40

    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=file_name,
        mimetype='application/pdf'
    )


@app.route("/process", methods=["POST"])
def process():
    form_data = request.form.to_dict()
    file = request.files["sample_pdf"]
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    upload_pdf_path = file_path
    uploaded_pdf_binary = file.read()
    file.seek(0)
    file.save(file_path)
    
    session["upload_name"] = filename
    form_data["sample_pdf"] = filename

    loader = PyMuPDFLoader(file_path)
    documents = loader.load()

    gas_data = extract_sample_gas_data(documents)
    if not gas_data:
        return render_template("index.html", report="No gas data found in uploaded PDF.")

    user_params = {
        "Appearance & Colour": form_data.get("appearance", ""),
        "Water content": form_data.get("water_content", ""),
        "Resistivity @ 90°C": form_data.get("resistivity", ""),
        "Tan Delta @90 °C": form_data.get("tan_delta", ""),
        "B.D.V @ 61.8Hz with stirrer": form_data.get("bdv", ""),
        "TRANSFORMER_ID": form_data.get("transformerid", ""),
        "Capacity": form_data.get("capacity", "")
    }
    capacity = form_data.get("capacity","")
    title = form_data.get("substationname", "")
    query = build_query(gas_data, user_params)
    print(query)
    results = vectorstore.similarity_search(query, k=3)
    print(f"\nTop {len(results)} similar results fetched:")
    for i, doc in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(f"Content:\n{doc.page_content[:300]}...")  # printing first 300 chars for brevity
        print(f"Metadata:\n{doc.metadata}")

    if not results:
        return render_template("index.html", report="No similar records found.")

    context = "\n\n".join([doc.page_content for doc in results])
    
    response = generate_response(context, query)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = []
    '''
    final_report = []

    final_report.append(f"                   AI DGA DIAGNOSIS Report    {timestamp}\n")
    #final_report.append(f"Title: {title}")
    final_report.append(f"Sample Name: {file_path}\n{'=' * 50}")
    final_report.append("Input:")
    for g in gas_data:
        final_report.append(f"{g['Gas Name']} = {g['PPM']} ppm")
    for key, val in form_data.items():
        if key != 'title':
            pretty_key = key.replace('_', ' ').title()
            final_report.append(f"{pretty_key} = {val}")
    final_report.append("-" * 60)
    final_report.append(response)
    final_report.append("-" * 60)
    '''
    final_report = []

    # Header section
    final_report.append(f"                   AI DGA DIAGNOSIS Report           {timestamp}\n{'=' * 50}")

    # Core details moved to top
    final_report.append(f"Substation Short Id = {form_data.get('substation_short_id', 'N/A')}")
    final_report.append(f"Substation Name     = {form_data.get('substation_name', 'N/A')}")
    final_report.append(f"Transformer ID       = {form_data.get('transformerid', 'N/A')}")
    final_report.append(f"Transformer Name     = {form_data.get('transformername', 'N/A')}")
    final_report.append(f"Capacity             = {form_data.get('capacity', 'N/A')}")
    # Title and sample
    #final_report.append(f"\nTitle: {title}")
    #final_report.append(f"Sample Name: {file_path}\n{'=' * 50}")

    # Gas input section
    final_report.append("=" * 60)
    final_report.append("Input:")
    for g in gas_data:
        final_report.append(f"{g['Gas Name']} = {g['PPM']} ppm")

    def typeone(key,val):
        standards_one = {
                            "B.D.V @ 61.8Hz with stirrer": {
                                "good": lambda v: v > 60,
                                "fair": lambda v: 50 <= v <= 60,
                                "poor": lambda v: v < 50,
                            },
                            "Tan Delta @90 °C": {
                                "good": lambda v: v < 0.1,
                                "fair": lambda v: 0.1 <= v <= 0.2,
                                "poor": lambda v: v > 0.2,
                            },
                            "Resistivity @ 90°C": {
                                "good": lambda v: v > 10,
                                "fair": lambda v: 3 <= v <= 10,
                                "poor": lambda v: v < 3,
                            },
                            "Water content": {
                                "good": lambda v: v < 15,
                                "fair": lambda v: 15 <= v <= 20,
                                "poor": lambda v: v > 20,
                            },
                        }

        if key in standards_one:
            for status, condition in standards_one[key].items():
                if condition(float(val)):
                    return status
            return "no standard"
    def typetwo(key, val):
        standards_two = {
                "B.D.V @ 61.8 Hz, With Stirrer": {
                    "good": lambda v: v > 50,
                    "fair": lambda v: 40 <= v <= 50,
                    "poor": lambda v: v < 40,
                },
                "Tan Delta @90°C, 55 Hz": {
                    "good": lambda v: v < 0.1,
                    "fair": lambda v: 0.1 <= v <= 0.5,
                    "poor": lambda v: v > 0.5,
                },
                "Resistivity @90°C": {
                    "good": lambda v: v > 3.0,
                    "fair": lambda v: 0.2 <= v <= 3.0,
                    "poor": lambda v: v < 0.2,
                },
                "Water Content": {
                    "good": lambda v: v < 20,
                    "fair": lambda v: 20 <= v <= 30,
                    "poor": lambda v: v > 30,
                },
                "Inter Facial Tension": {
                    "good": lambda v: v > 28,
                    "fair": lambda v: 22 <= v <= 28,
                    "poor": lambda v: v < 22,
                },
                "Acidity": {
                    "good": lambda v: v < 0.1,
                    "fair": lambda v: 0.1 <= v <= 0.2,
                    "poor": lambda v: v > 0.2,
                },
            }
        if key in standards_two:
            for status, condition in standards_two[key].items():
                if condition(float(val)):
                    return status
            return "no standard"
    # Other parameters
    standone= False
    if capacity>170 :
        standone = True
    
    for key, val in user_params.items():
        if key not in ['title', 'substation_short_id', 'substation_name', 'transformerid', 'transformername', 'capacity','sample_pdf','Capacity', 'transformer_id']:
            pretty_key = key.replace('_', ' ').title()
            if standone:
                status = typeone(key, val)
            else:
                status = typetwo(key, val)
            final_report.append(f"{pretty_key} = {val} ({status})")

    final_report.append("-" * 60)
    final_report.append(response)
    final_report.append("-" * 60)


    cleaned_response = response.strip().replace('\nRemarks:', 'Remarks:').replace('\nPreventive Steps:', 'Preventive Steps:')
    report.append(cleaned_response)
    #report.append(context)

    reference_docs = []

    for i, doc in enumerate(results, 1):
        source_path = doc.metadata.get("source", "")
        if not os.path.exists(source_path):
            continue

        file_name = os.path.basename(source_path)
        dest_path = os.path.join(DOCS_FOLDER, file_name)

        if not os.path.exists(dest_path):
            try:
                with open(source_path, "rb") as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
            except Exception as e:
                print(f"Error copying {file_name}: {e}")
                continue

        reference_docs.append({
            "index": i,
            "source": file_name,
            "url": url_for('static', filename=f'docs/{file_name}')
        })

        final_report.append(f"Reference {i}")
        final_report.append(f"source: {file_name}")
        final_report.append("-" * 60)

    session["last_report"] = "\n".join(report)
    session["final_report"] = "\n".join(final_report)

    cur.execute("SELECT substation_short_id, substation_name FROM substation_master")
    substations = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("SELECT substation_short_id, transformer_id, transformer_name, transformer_capacity FROM transformer_master")
    transformer_map = {}
    for sid, tid, tname, cap in cur.fetchall():
        if sid not in transformer_map:
            transformer_map[sid] = {}
        transformer_map[sid][tid] = {
            "transformer_name":tname,
            "transformer_capacity": cap
            }
    test_input_json = {
    "parameters": {
        "gases": {g["Gas Name"]: g["PPM"] for g in gas_data},
        "form_inputs": {
            "Appearance & Colour": form_data.get("appearance", ""),
            "Water content": form_data.get("water_content", ""),
            "Resistivity @ 90°C": form_data.get("resistivity", ""),
            "Tan Delta @90 °C": form_data.get("tan_delta", ""),
            "B.D.V @ 61.8Hz with stirrer": form_data.get("bdv", ""),
            "TRANSFORMER_ID": form_data.get("transformerid", ""),
            "Capacity": form_data.get("capacity", "")
            }
        }
    }

    # Generate PDF in memory
    pdf_buffer = BytesIO()
    p = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    for line in session["final_report"].split("\n"):
        wrapped = wrap(line, width=100)
        for part in wrapped:
            p.drawString(40, y, part)
            y -= 15
            if y < 40:
                p.showPage()
                y = height - 40
    p.save()
    pdf_buffer.seek(0)
    report_pdf_binary = pdf_buffer.read()

    # 4. Insert into dga_results
    insert_query = """
    INSERT INTO dga_results (
        substation_id,
        transformer_id,
        testing_date,
        test_input_json,
        ai_response,
        ai_reference_json,
        report_pdf,
        uploaded_pdf,
        upload_pdf_path
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    insert_values = (
        form_data.get("substation_short_id"),
        form_data.get("transformerid"),
        datetime.now(),
        json.dumps(test_input_json),
        response,
        json.dumps(reference_docs),
        psycopg2.Binary(report_pdf_binary),
        psycopg2.Binary(uploaded_pdf_binary),
        upload_pdf_path
    )

    try:
        cur.execute(insert_query, insert_values)
        conn.commit()
    except Exception as e:
        print(f"Database insert failed: {e}")

    return render_template("index.html", report=session["last_report"], form_data=form_data, references=reference_docs, substations=substations, transformers=transformer_map)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)
