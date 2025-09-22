import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from openai import OpenAI

# Google OAuth credentials
CLIENT_CONFIG = {
    "installed": {
        "client_id": "1063438628357-r5ef5vu4195aqanhcur1gagvhc9r5heg.apps.googleusercontent.com",
        "project_id": "Caregiver App",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["http://localhost:8080/"]  # Update when deployed
    }
}

CAREGIVER_FOLDER_ID = "1tufdKiVKyO4ZdrVrkVLq8jqBPJkZnV2-"
TARGET_DOC_NAME = "Johann Life Guide"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# --- Google Drive helpers ---
def init_drive():
    flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
    creds = flow.run_local_server(port=8080)
    return build("drive", "v3", credentials=creds)

def get_target_doc(service):
    query = f"'{CAREGIVER_FOLDER_ID}' in parents and name = '{TARGET_DOC_NAME}'"
    results = service.files().list(
        q=query,
        pageSize=1,
        fields="files(id, name, mimeType)"
    ).execute()
    files = results.get("files", [])
    return files[0] if files else None

def get_google_doc_text(service, file_id):
    request = service.files().export(fileId=file_id, mimeType="text/plain")
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    text = fh.read().decode("utf-8")
    return text

# --- OpenAI ---
def ask_question(client, text, question):
    prompt = f"Here is information about Johann:\n\n{text}\n\nQuestion: {question}\nAnswer only based on this text."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# --- Streamlit App ---
def main():
    st.title("Caregiver App - Johann Life Guide")

    # Session state for multi-user support
    if "creds" not in st.session_state:
        st.session_state.creds = None
    if "knowledge_text" not in st.session_state:
        st.session_state.knowledge_text = ""
    if "openai_key" not in st.session_state:
        st.session_state.openai_key = None

    # --- API Key Input ---
    if not st.session_state.openai_key:
        api_key_input = st.text_input("Enter your OpenAI API Key:", type="password")
        if api_key_input:
            st.session_state.openai_key = api_key_input
            st.success("✅ API key saved in session!")
    else:
        st.success("🔑 API key already set")
        if st.button("Reset API Key"):
            st.session_state.openai_key = None
            st.info("API key cleared. Please re-enter.")
            return

    # --- Guard: Only proceed if API key is set ---
    if st.session_state.openai_key:
        client = OpenAI(api_key=st.session_state.openai_key)
    else:
        st.warning("Please enter your OpenAI API key above to continue.")
        st.stop()

    # --- Login with Google ---
    if st.session_state.creds is None:
        if st.button("Login with Google"):
            service = init_drive()
            st.session_state.creds = service._http.credentials
            st.success("✅ Logged in successfully!")

    # --- After login ---
    if st.session_state.creds:
        service = build("drive", "v3", credentials=st.session_state.creds)

        # Load knowledge base once per session
        if not st.session_state.knowledge_text:
            st.info("Loading Johann Life Guide from Google Drive...")
            doc = get_target_doc(service)
            if doc:
                st.session_state.knowledge_text = get_google_doc_text(service, doc['id'])
                st.success("Knowledge base loaded!")
            else:
                st.warning(f"'{TARGET_DOC_NAME}' not found in caregiver folder.")
                return

        # Question input
        question = st.text_input("Ask a question about Johann")
        if question:
            with st.spinner("Getting answer..."):
                answer = ask_question(client, st.session_state.knowledge_text, question)
            st.subheader("Answer:")
            st.write(answer)

if __name__ == "__main__":
    main()
