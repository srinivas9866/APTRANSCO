from flask import Flask, send_file, request, abort
import psycopg2
from io import BytesIO

app = Flask(__name__)

# PostgreSQL connection
conn = psycopg2.connect(
    dbname="RAG",
    user="postgres",
    password="srinivas@123",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

@app.route("/download_report/<int:object_id>")
def download_report(object_id):
    print(f"Fetching uploaded_pdf for object_id: {object_id}")
    cur.execute("SELECT uploaded_pdf FROM dga_results WHERE object_id = %s", (object_id,))
    row = cur.fetchone()
    print(f"Row fetched: {row}")

    if not row or not row[0]:
        print("PDF not found in uploaded_pdf.")
        return abort(404, "PDF not found.")

    return send_file(
        BytesIO(row[0]),
        as_attachment=True,
        download_name=f"report_{object_id}.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run(debug=True)
