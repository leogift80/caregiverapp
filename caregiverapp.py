import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from openai import OpenAI
import json

st.set_page_config(page_title="Caregiver App", layout="centered")
st.title("Caregiver App - Personalized Life Guide")

# ---------------------------
# Session state
# ---------------------------
if "creds" not in st.session_state:
    st.session_state.creds = None
if "knowledge_text" not in st.session_state:
    st.session_state.knowledge_text = ""
if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""

# ---------------------------
# OpenAI key input
# ---------------------------
if not st.session_state.openai_key:
    st.session_state.openai_key = st.text_input(
        "Enter your OpenAI API key (sk-...)", type="password"
    )

client = OpenAI(api_key=st.session_state.openai_key) if st.session_state.openai_key else None

# ---------------------------
# Google OAuth setup
# ---------------------------
CLIENT_CONFIG = st.secrets["google_oauth"]
CLIENT_CONFIG = {"web": CLIENT_CONFIG["web"]}
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Streamlit URL for redirect
STREAMLIT_URL = st.secrets["streamlit_url"]  # add your app URL in secrets.toml

# ---------------------------
# Helper functions
# ---------------------------
def init_drive(creds):
    return build("drive", "v3", credentials=creds)

def get_google_doc_text(service, file_id):
    request = service.files().export(fileId=file_id, mimeType="text/plain")
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read().decode("utf-8")

def list_files_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    return results.get("files", [])

def ask_question(text, question):
    prompt = f"Here is information about your child:\n\n{text}\n\nQuestion: {question}\nAnswer only based on this text."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# ---------------------------
# Google OAuth flow
# ---------------------------
from urllib.parse import parse_qs
query_params = st.experimental_get_query_params()

if not st.session_state.creds:
    if "code" in query_params:
        # Callback from Google OAuth
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        flow.redirect_uri = STREAMLIT_URL
        flow.fetch_token(code=query_params["code"][0])
        st.session_state.creds = flow.credentials
        st.experimental_set_query_params()  # clear query params
        st.success("✅ Logged in to Google Drive!")
    else:
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        flow.redirect_uri = STREAMLIT_URL
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        st.markdown(f"[Click here to login with Google]({auth_url})")
        st.stop()

# ---------------------------
# Main app after login
# ---------------------------
service = init_drive(st.session_state.creds)

st.header("Step 1: Select or create a folder for your child")
folder_name = st.text_input("Enter folder name (existing or new):", value="Child Life Guide")

folders = list_files_in_folder(service, "root")
folder = next((f for f in folders if f["name"] == folder_name and f["mimeType"]=="application/vnd.google-apps.folder"), None)

if not folder and folder_name:
    file_metadata = {"name": folder_name, "mimeType":"application/vnd.google-apps.folder"}
    folder = service.files().create(body=file_metadata, fields="id, name").execute()
    st.success(f"Folder '{folder_name}' created!")

folder_id = folder["id"]

st.header("Step 2: Upload or select documents")
uploaded_file = st.file_uploader("Upload a text file (optional)", type=["txt"])

if uploaded_file:
    st.session_state.knowledge_text = uploaded_file.read().decode("utf-8")
    st.success("File uploaded!")

if not st.session_state.knowledge_text:
    files = list_files_in_folder(service, folder_id)
    doc = next((f for f in files if f["mimeType"]=="application/vnd.google-apps.document"), None)
    if doc:
        st.session_state.knowledge_text = get_google_doc_text(service, doc["id"])
        st.success(f"Loaded '{doc['name']}' from Google Drive")

st.header("Step 3: Ask a question")
question = st.text_input("Type your question:")
if question and st.session_state.knowledge_text and client:
    with st.spinner("Getting answer..."):
        answer = ask_question(st.session_state.knowledge_text, question)
    st.subheader("Answer:")
    st.write(answer)
