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
    st.caption("Switch models if you hit a Rate Limit error.")
    model_choice = st.selectbox(
        "Choose Model:",
        ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash"],
        index=0
    )
    st.divider()
    st.info(f"Active Model: **{model_choice}**")

# --- MAIN APP ---
st.title("🏭 Industrial OEM Identifier")
st.markdown(f"Identify manufacturers using **{model_choice}** + **Google Search**.")

# --- INPUT METHOD SELECTION ---
tab1, tab2 = st.tabs(["📁 Upload File", "📝 Paste Text"])

df = None
part_col = "Part Number" # Default name for text input

# --- TAB 1: FILE UPLOAD ---
with tab1:
    uploaded_file = st.file_uploader("Upload Excel or CSV", type=['xlsx', 'xls', 'csv'])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.write("Preview:")
            st.dataframe(df.head(3), use_container_width=True)
            
            # Let user pick the column if uploading a file
            part_col = st.selectbox("Select the column containing PART NUMBERS:", df.columns)
            
        except Exception as e:
            st.error(f"Error reading file: {e}")

# --- TAB 2: PASTE TEXT ---
with tab2:
    st.markdown("Paste your part numbers below (one per line):")
    text_input = st.text_area("Part Numbers", height=200, placeholder="1794-AENTR\n6ES7-300\nFX3U-32M")
    
    if text_input:
        # Convert text input into a DataFrame
        lines = [line.strip() for line in text_input.split('\n') if line.strip()]
        if lines:
            df = pd.DataFrame(lines, columns=["Part Number"])
            part_col = "Part Number" # Set the column name automatically
            st.info(f"Loaded {len(lines)} parts from text.")

# --- PROCESSING LOGIC (Common for both) ---
if df is not None:
    if st.button("🚀 Identify OEMs", type="primary"):
        if not api_key:
            st.error("⚠️ Please enter your Gemini API Key in the sidebar first!")
        else:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=model_choice,
                tools='google_search_retrieval'
            )
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            unique_parts = df[part_col].dropna().unique().tolist()
            total_parts = len(unique_parts)
            results_map = {}
            BATCH_SIZE = 5
            
            for i in range(0, total_parts, BATCH_SIZE):
                batch = unique_parts[i:i + BATCH_SIZE]
                status_text.text(f"Processing batch {i//BATCH_SIZE + 1}...")
                
                prompt = f"""
                Act as an industrial supply chain expert. Identify the Manufacturer (OEM) or Brand for these part numbers: {', '.join(map(str, batch))}.
                Context: Industrial Automation, Electrical, or Mechanical spares.
                Instructions:
                1. Search the web for each part.
                2. Return ONLY a list of Company Names separated by a pipe symbol (|) in the exact same order.
                3. If famous brand (e.g. 'Allen-Bradley'), return Brand or Parent.
                4. If unknown, write 'Unknown'.
                """
                
                try:
                    response = model.generate_content(prompt)
                    clean_text = response.text.strip()
                    batch_results = [x.strip() for x in clean_text.split('|')]
                    
                    if len(batch_results) != len(batch):
                        batch_results = ["Error/Mismatch"] * len(batch)
                    
                    for part, result in zip(batch, batch_results):
                        results_map[part] = result
                        
                except Exception as e:
                    st.error(f"Error: {e}")
                    if "429" in str(e):
                        st.warning("Rate Limit! Switch model in sidebar.")
                    for part in batch:
                        results_map[part] = "Error"
                
                progress_bar.progress(min((i + BATCH_SIZE) / total_parts, 1.0))
                time.sleep(2)
            
            # Add results to DataFrame
            df['Identified_OEM'] = df[part_col].map(results_map)
            
            status_text.success("✅ Done!")
            st.dataframe(df, use_container_width=True)
            
            # Download Button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Results", csv, "oem_results.csv", "text/csv")

elif st.button("🚀 Identify OEMs"):
    st.warning("Please upload a file OR paste text first.")
