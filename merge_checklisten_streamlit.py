import streamlit as st
import os
import io
import zipfile
import base64
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd
from datetime import datetime

# === Hilfsfunktionen ===

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def extract_maengel_by_checkliste(maengel_pdf):
    checkliste_to_pages = {}
    reader = PdfReader(maengel_pdf)
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            for line in text.split("\n"):
                if "Checkliste:" in line:
                    parts = line.split("Checkliste:")
                    if len(parts) > 1:
                        nr = parts[1].strip()
                        if nr not in checkliste_to_pages:
                            checkliste_to_pages[nr] = set()
                        checkliste_to_pages[nr].add(i)  # set statt liste

    # In sortierte Liste umwandeln, um Reihenfolge zu behalten
    return {k: sorted(v) for k, v in checkliste_to_pages.items()}

def get_checklistennummer_from_filename(filename):
    return os.path.splitext(os.path.basename(filename))[0]

def merge_pdfs(checklist_pdf, maengel_pages, maengel_reader):
    writer = PdfWriter()
    reader_check = PdfReader(checklist_pdf)
    
    for page in reader_check.pages:
        writer.add_page(page)
    
    for i in maengel_pages:
        writer.add_page(maengel_reader.pages[i])
    
    output_stream = io.BytesIO()
    writer.write(output_stream)
    output_stream.seek(0)
    return output_stream

# === Streamlit UI ===

st.set_page_config(page_title="Checklisten-Merger", layout="centered")

# Logo anzeigen (aus Repository)
logo_path = "Halter_Logo_Anthrazit_RGB_Online.png"
try:
    img_base64 = get_base64_image(logo_path)
    st.markdown(
        f"""
        <div style='text-align: left; margin-bottom: 10px;'>
            <img src="data:image/png;base64,{img_base64}" width="250" style="border-radius: 0px;">
        </div>
        """,
        unsafe_allow_html=True
    )
except:
    st.warning("Logo konnte nicht geladen werden.")

st.title("Dalux Field")
st.title("Abnahmeprotokolle & Mängelliste zusammenführen")

checklist_files = st.file_uploader("📄 Abnahmeprotokolle (mehrere PDFs)", type="pdf", accept_multiple_files=True)
maengel_file = st.file_uploader("📋 Mängelliste (eine PDF)", type="pdf")

if st.button("✅ Verarbeiten") and checklist_files and maengel_file:

    maengel_reader = PdfReader(maengel_file)
    checkliste_to_pages = extract_maengel_by_checkliste(maengel_file)

    zip_buffer = io.BytesIO()
    excel_rows = []

    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for checklist_file in checklist_files:
            checklist_number = get_checklistennummer_from_filename(checklist_file.name)
            maengel_pages = checkliste_to_pages.get(checklist_number, [])

            merged_pdf = merge_pdfs(checklist_file, maengel_pages, maengel_reader)

            merged_name = f"{checklist_number}_zusammengefuehrt.pdf"
            zipf.writestr(merged_name, merged_pdf.read())

            excel_rows.append({
                "Checkliste": checklist_number,
                "Mängel-Seiten": ", ".join(str(p+1) for p in maengel_pages) if maengel_pages else "Keine"
            })

        # Excel erstellen
        df = pd.DataFrame(excel_rows)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        zipf.writestr("Übersicht.xlsx", excel_buffer.getvalue())

    zip_buffer.seek(0)

    st.success("✅ Verarbeitung abgeschlossen!")

    # Download-Link
    st.download_button(
        label="📥 ZIP-Datei herunterladen",
        data=zip_buffer,
        file_name=f"Checklisten_Merged_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.zip",
        mime="application/zip"
    )
