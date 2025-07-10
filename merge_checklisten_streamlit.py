import os
import re
import shutil
import tempfile
from PIL import Image

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd
import base64

def extrahiere_maengel_nach_checkliste(maengel_pdf_path):
    seiten_dict = {}
    with pdfplumber.open(maengel_pdf_path) as pdf:
        for i, seite in enumerate(pdf.pages):
            text = seite.extract_text()
            if not text:
                continue
            matches = re.findall(r"Checkliste:\s*([^\s]+)", text)
            unique_ids = set(matches)
            for nummer in unique_ids:
                nummer = nummer.strip()
                if nummer not in seiten_dict:
                    seiten_dict[nummer] = set()
                seiten_dict[nummer].add(i)
    return {k: sorted(v) for k, v in seiten_dict.items()}


def fuege_pdfs_zusammen(maengel_path, abnahme_ordner, ausgabe_ordner, seiten_dict):
    maengel_reader = PdfReader(maengel_path)
    os.makedirs(ausgabe_ordner, exist_ok=True)

    erfolge = []
    fehler = []
    daten_fuer_excel = []

    # Alle Checklisten im Abnahmeordner durchgehen
    for datei in os.listdir(abnahme_ordner):
        if not datei.endswith(".pdf"):
            continue

        nummer = os.path.splitext(datei)[0]
        abnahme_pfad = os.path.join(abnahme_ordner, datei)
        ausgabe_pfad = os.path.join(ausgabe_ordner, f"{nummer}_mit_Maengeln.pdf")

        writer = PdfWriter()
        try:
            abnahme_reader = PdfReader(abnahme_pfad)
            for seite in abnahme_reader.pages:
                writer.add_page(seite)

            maengel_seiten = seiten_dict.get(nummer, [])

            for i in maengel_seiten:
                writer.add_page(maengel_reader.pages[i])

            with open(ausgabe_pfad, "wb") as f_out:
                writer.write(f_out)

            erfolge.append(f"✅ {nummer} verarbeitet ({len(maengel_seiten)} Mängel-Seiten)")
            daten_fuer_excel.append({
                "Checkliste": nummer,
                "Mängel-Seiten": len(maengel_seiten),
                "Ausgabepfad": ausgabe_pfad
            })

        except Exception as e:
            fehler.append(f"⚠️ Fehler bei {nummer}: {e}")
            daten_fuer_excel.append({
                "Checkliste": nummer,
                "Mängel-Seiten": "⚠️",
                "Ausgabepfad": f"Fehler: {e}"
            })

    return erfolge, fehler, daten_fuer_excel



st.set_page_config(page_title="Checklisten-Merger", layout="centered")

# === Logo anzeigen ohne Abrundung ===
logo_path = "Halter_Logo_Anthrazit_RGB_Online.png"

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

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
except Exception as e:
    st.warning(f"Logo konnte nicht geladen werden: {e}")

st.title("Dalux Field")
st.title("Abnahmeprotokolle & Mängelliste zusammenführen")


maengel_pdf = st.file_uploader("🔍 Mängelliste (PDF)", type=["pdf"])
abnahme_ordner = st.text_input("📂 Pfad zum Abnahmeprotokoll-Ordner", value="Pfad angeben: C:\...  ('""' löschen) ")
ausgabe_ordner = st.text_input("💾 Zielordner für Ausgabe", value="Pfad angeben: C:\... ('""' löschen)")

if st.button("🚀 Verarbeiten"):
    if not maengel_pdf:
        st.error("Bitte lade eine Mängelliste hoch.")
    elif not os.path.isdir(abnahme_ordner):
        st.error("Der Abnahmeprotokoll-Ordner ist ungültig.")
    else:
        with st.spinner("🔄 Verarbeite PDFs..."):

            # Temporäre Datei für hochgeladenes PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(maengel_pdf.read())
                maengel_path = tmp.name

            seiten_dict = extrahiere_maengel_nach_checkliste(maengel_path)
            erfolge, fehler, daten_fuer_excel = fuege_pdfs_zusammen(
                maengel_path, abnahme_ordner, ausgabe_ordner, seiten_dict
            )

            # Excel-Datei erzeugen
            excel_df = pd.DataFrame(daten_fuer_excel)
            excel_path = os.path.join(ausgabe_ordner, "uebersicht_checklisten.xlsx")
            excel_df.to_excel(excel_path, index=False)

        st.success("✅ Verarbeitung abgeschlossen!")

        if erfolge:
            st.subheader("✅ Erfolgreich:")
            st.write("\n".join(erfolge))

        if fehler:
            st.subheader("⚠️ Fehler / Warnungen:")
            st.warning("\n".join(fehler))

        st.subheader("📊 Excel-Übersicht:")
        st.dataframe(excel_df)

        with open(excel_path, "rb") as f:
            st.download_button("📥 Excel herunterladen", f, file_name="uebersicht_checklisten.xlsx")
