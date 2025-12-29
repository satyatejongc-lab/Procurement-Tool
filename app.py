import streamlit as st
import pandas as pd
import google.generativeai as genai
import time
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="OEM Part Identifier", page_icon="🏭", layout="wide")

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    
    st.markdown("### 🤖 Select Model")
    model_choice = st.selectbox(
        "Choose Model:",
        ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash"],
        index=0
    )
    st.info(f"Active Model: **{model_choice}**")

# --- MAIN APP ---
st.title("🏭 Industrial OEM Identifier")

# --- TABS FOR INPUT ---
tab1, tab2 = st.tabs(["📁 Upload File", "📝 Paste Text"])

df = None
part_col = "Part Number"

# --- TAB 1: FILE UPLOAD ---
with tab1:
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'xls', 'csv'])
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(3), use_container_width=True)
        part_col = st.selectbox("Select Column:", df.columns)

# --- TAB 2: PASTE TEXT ---
with tab2:
    st.write("Paste part numbers below (one per line):")
    text_input = st.text_area("Part Numbers", height=200, placeholder="1794-AENTR\n6ES7-300")
    if text_input:
        lines = [line.strip() for line in text_input.split('\n') if line.strip()]
        if lines:
            df = pd.DataFrame(lines, columns=["Part Number"])
            part_col = "Part Number"
            st.info(f"Loaded {len(lines)} parts.")

# --- PROCESSING ---
if df is not None and st.button("🚀 Identify OEMs", type="primary"):
    if not api_key:
        st.error("⚠️ Enter API Key in sidebar first!")
    else:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_choice, tools='google_search_retrieval')
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        unique_parts = df[part_col].dropna().unique().tolist()
        results_map = {}
        BATCH_SIZE = 5
        
        for i in range(0, len(unique_parts), BATCH_SIZE):
            batch = unique_parts[i:i + BATCH_SIZE]
            status_text.text(f"Processing batch {i//BATCH_SIZE + 1}...")
            
            prompt = f"Identify OEM for: {', '.join(map(str, batch))}. Return ONLY Company Names separated by pipe (|)."
            
            try:
                response = model.generate_content(prompt)
                results = [x.strip() for x in response.text.split('|')]
                if len(results) != len(batch): results = ["Error"] * len(batch)
                for part, res in zip(batch, results): results_map[part] = res
            except:
                for part in batch: results_map[part] = "Error"
            
            progress_bar.progress(min((i + BATCH_SIZE) / len(unique_parts), 1.0))
            time.sleep(1)
            
        df['Identified_OEM'] = df[part_col].map(results_map)
        status_text.success("Done!")
        st.dataframe(df, use_container_width=True)
