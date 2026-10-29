# Multimodal Construction Intelligence Platform

Skill Wallet Capstone Project 1. Streamlit + Google Gemini. No database required.

## Run locally
    pip install -r requirements.txt
    streamlit run app.py

## Deploy on Streamlit Community Cloud
1. Push `app.py`, `requirements.txt` and `.streamlit/` to a GitHub repo.
2. Create a new app on share.streamlit.io pointing to `app.py`.
3. Optional: add `GEMINI_API_KEY = "your-key"` under App settings > Secrets so visitors skip the key field.

Without a key the app runs in demonstration mode with realistic sample outputs.
