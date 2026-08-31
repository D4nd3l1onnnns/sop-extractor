import streamlit as st
import os
import tempfile
import re
import requests
from google import genai

# Konfigurasi Tampilan Halaman Web
st.set_page_config(page_title="SOP AI Extractor", page_icon="🏥", layout="centered")

st.title("🏥 SOP AI Extractor & Checker")
st.write("Sistem cerdas berbasis AI untuk mengekstrak poin **Tujuan** dan **Unit Terkait** dari dokumen SOP secara instan tanpa ribet.")

# Inisialisasi session_state untuk menyimpan API Key agar tidak hilang saat refresh
if "api_key_input" not in st.session_state:
    st.session_state.api_key_input = ""

# Menu Sidebar untuk Memasukkan API Key secara Aman
st.sidebar.header("Konfigurasi Sistem")
api_key = st.sidebar.text_input(
    "Gemini API Key", 
    value=st.session_state.api_key_input, 
    type="password",
    key="input_key_widget"
)

if api_key:
    st.session_state.api_key_input = api_key

if not st.session_state.api_key_input:
    st.warning("⚠️ Masukkan Gemini API Key terlebih dahulu di menu sidebar sebelah kiri.")
    st.info("💡 Belum punya API Key? Ambil gratis di [Google AI Studio](https://aistudio.google.com/).")

# Tombol untuk Bersihkan / Reset Form Dokumen Baru
col1, col2 = st.columns([0.8, 0.2])
with col1:
    drive_url = st.text_input("Tempel Link Google Drive File SOP (Pastikan akses disetel 'Anyone with the link can view'):")
with col2:
    st.write("") 
    if st.button("🔄 Reset Form"):
        st.rerun()

# Fungsi Caching untuk mempercepat proses download & upload file agar tidak berulang
@st.cache_data(show_spinner=False)
def get_ai_file_from_drive(url, current_api_key):
    # Ekstrak File ID unik dari Link Google Drive
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        match = re.search(r'id=([a-zA-Z0-9-_]+)', url)
    
    if not match:
        raise ValueError("Format link Google Drive tidak valid!")
    
    file_id = match.group(1)
    download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
    response = requests.get(download_url)
    
    if response.status_code != 200:
        raise ConnectionError("Gagal mendownload file. Pastikan file di-share publik ('Anyone with the link can view').")
        
    # Simpan file PDF sementara di sistem
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(response.content)
        pdf_path = tmp.name

    # Inisialisasi client dan upload file ke server Gemini
    client = genai.Client(api_key=current_api_key)
    ai_file = client.files.upload(file=pdf_path)
    
    # Hapus file temp lokal
    os.remove(pdf_path)
    
    return ai_file.name

# Tombol Eksekusi Proses
if st.button("🚀 Analisis Dokumen SOP", type="primary"):
    current_key = st.session_state.api_key_input
    if not current_key:
        st.error("Gemini API Key belum dimasukkan!")
    elif not drive_url:
        st.error("Silakan masukkan link Google Drive terlebih dahulu!")
    else:
        with st.spinner("🤖 AI sedang membaca seluruh isi dokumen SOP secara kilat..."):
            try:
                client = genai.Client(api_key=current_key)
                
                # Panggil fungsi cache untuk mendapatkan file di server Gemini
                file_name = get_ai_file_from_drive(drive_url, current_key)
                
                # Ambil kembali objek file dari server menggunakan namanya
                ai_file = client.files.get(name=file_name)
                
                # Perintah / Prompt khusus untuk AI
                prompt = """
                Analisis dokumen SOP Rumah Sakit ini secara mendalam. Ekstrak dan format hasilnya persis seperti ini:
                
                [PERIHAL / JUDUL]
                (tuliskan judul atau perihal dokumen dengan jelas)
                
                [UNIT TERKAIT]
                (sebutkan seluruh nomor dan daftar unit terkait secara lengkap sesuai isi dokumen tanpa terpotong)
                
                [TUJUAN]
                (sebutkan seluruh nomor dan poin tujuan secara lengkap sesuai isi dokumen tanpa terpotong)
                """
                
                # Daftar model cadangan (Fallback beruntun untuk mengantisipasi error server sibuk)
                daftar_model = ['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-1.5-flash']
                hasil_teks = None
                sukses = False

                for nama_model in daftar_model:
                    try:
                        response = client.models.generate_content(
                            model=nama_model,
                            contents=[ai_file, prompt]
                        )
                        hasil_teks = response.text
                        sukses = True
                        break
                    except Exception:
                        continue

                if not sukses or not hasil_teks:
                    st.error("Semua server model Gemini sedang sibuk atau mengalami gangguan sementara. Silakan coba beberapa saat lagi.")
                    st.stop()
                
                # Tampilkan hasil di layar web
                st.success("✅ Analisis Dokumen Berhasil!")
                st.markdown("---")
                st.markdown("### Hasil Ekstraksi:")
                st.markdown(hasil_teks)
                
                # Kotak Teks Khusus (Agar mudah disalin/copy)
                st.markdown("---")
                st.text_area("Kotak Teks Siap Salin:", value=hasil_teks, height=300)
                
            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {str(e)}")
