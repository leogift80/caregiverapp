import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os

# ==========================
# Google OAuth Configuration
# ==========================
CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["google"]["client_id"],
        "project_id": st.secrets["google"]["project_id"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": st.secrets["google"]["client_secret"],
        "redirect_uris": [st.secrets["google"]["redirect_uri"]],
    }
}

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

st.set_page_config(page_title="Caregiver App", page_icon="👨‍👩‍👧")
st.title("👨‍👩‍👧 Caregiver App")

# ==========================
# Session State
# ==========================
if "creds" not in st.session_state:
    st.session_state.creds = None

# ==========================
# OAuth Flow
# ==========================
flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
flow.redirect_uri = st.secrets["google"]["redirect_uri"]

auth_url, _ = flow.authorization_url(
    access_type="offline",
    include_granted_scopes="true",
    prompt="consent",
)

query_params = st.query_params

if "code" in query_params and st.session_state.creds is None:
    try:
        flow.fetch_token(code=query_params["code"][0])
        st.session_state.creds = flow.credentials

        # ✅ Clear URL after success
        st.query_params.clear()
        st.success("✅ Logged in with Google!")
    except Exception as e:
        st.error("OAuth failed. Please try logging in again.")
        st.write(str(e))
        st.query_params.clear()  # clear bad state

# ==========================
# App Logic (After Login)
# ==========================
if st.session_state.creds:
    st.success("You’re logged in ✅")

    try:
        # Connect to Google Drive
        service = build("drive", "v3", credentials=st.session_state.creds)

        st.subheader("📂 Your Drive Files")
        results = service.files().list(
            pageSize=5, fields="files(id, name)"
        ).execute()
        items = results.get("files", [])

        if not items:
            st.write("No files found in Drive.")
        else:
            for file in items:
                st.write(f"📄 {file['name']} ({file['id']})")

        # Upload new file
        uploaded_file = st.file_uploader("Upload a file for your child")
        if uploaded_file:
            file_metadata = {"name": uploaded_file.name}
            media = uploaded_file.getvalue()
            drive_file = service.files().create(
                body=file_metadata,
                media_body=st.file_uploader,
                fields="id"
            ).execute()
            st.success(f"✅ File uploaded: {uploaded_file.name}")

    except Exception as e:
        st.error("⚠️ Something went wrong while accessing Google Drive.")
        st.write(str(e))

else:
    st.markdown(f"[🔑 Login with Google]({auth_url})")
