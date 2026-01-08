import re
import requests
import json


def extract_sample_gas_data(documents):
    combined_text = "\n".join(doc.page_content for doc in documents)
    pattern = r"(\d+\.\d+)\s+\d\s+(?:BB\s+\+I|BV\s+\+I|VBA\s+\+I)?\s*[\d\.Ee+-]*\s*[\d\.Ee+-]*\s*([\d\.Ee+-]+|-)\s+(\w+)"
    matches = re.findall(pattern, combined_text)

    gas_data = []
    for ret, ppm, name in matches:
        if ppm != "-":
            gas_data.append({"Gas Name": name, "PPM": ppm})
        else:
            gas_data.append({"Gas Name": name, "PPM": "Not Detected"})
    return gas_data

def build_query(gas_data, user_parameters):
    gas_parts = [f"{row['Gas Name']}={row['PPM']}" for row in gas_data]
    param_parts = [f"{k}={v}" for k, v in user_parameters.items() if v.strip()]
    return ", ".join(gas_parts + param_parts)

def generate_response(context, query):
    url = "http://localhost:11434/api/generate"
    #url = "http://10.96.76.121:11434/api/generate"
    payload = {
        "model": "gemma3",
        "prompt": (
            "You are a helpful assistant to perform transformer oil testing to assess the transformer health. "
            "Use the following context and chat history to answer the question accurately.\n\n"
            f"Context:\n{context}\n\n neglect this if it is not relevant"
            f"Question:\n {query}\n"
            "Answer: Provide only remarks and preventive steps in this format:"
            "In remarks definitely mention whether gases levels are satisfactory or not"
            "Remarks:\n<your remarks>\n\n"
            "Preventive Steps: \n <your preventive steps in points>\n"
            "Do not include anything else."
        ),
        "stream": True
    }

    reply = ""
    try:
        response = requests.post(url, json=payload, stream=True)
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            line = line.strip()
            if line.startswith("{"):
                try:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    print(token, end="", flush=True)
                    reply += token
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"\n[Error during response generation: {e}]")
    print()

    reply = reply.strip()
    if not reply.startswith("Remarks:"):
        reply = "Remarks: (Missing)\nPreventive Steps: (Missing)"
    return reply