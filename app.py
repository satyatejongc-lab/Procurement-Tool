import streamlit as st
import pandas as pd
import google.generativeai as genai
import time
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="OEM Part Identifier (Debug)", page_icon="🐞", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    st.markdown("### 🤖 Select Model")
    model_choice = st.selectbox(
        "Choose Model:",
        ["gemini-2.0-flash-exp", "gemini-1.5-flash"], # Updated to most stable search models
        index=1
    )
    st.info(f"Active Model: **{model_choice}**")

# --- MAIN APP ---
st.title("🐞 OEM Identifier (Debug Mode)")
st.error("Debug Mode is ON. Detailed errors will appear below.")

# --- TABS ---
tab1, tab2 = st.tabs(["📁 Upload File", "📝 Paste Text"])

df = None
part_col = "Part Number"

with tab1:
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'xls', 'csv'])
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(3), use_container_width=True)
        part_col = st.selectbox("Select Column:", df.columns)

with tab2:
    text_input = st.text_area("Paste Part Numbers (one per line)", height=150, placeholder="1794-AENTR\n6ES7-300")
    if text_input:
        lines = [line.strip() for line in text_input.split('\n') if line.strip()]
        if lines:
            df = pd.DataFrame(lines, columns=["Part Number"])
            part_col = "Part Number"

# --- PROCESSING ---
if df is not None and st.button("🚀 Identify OEMs"):
    if not api_key:
        st.error("⚠️ Enter API Key in sidebar first!")
    else:
        genai.configure(api_key=api_key)
        # Using a safer tool configuration for search
        tools_config = {'google_search_retrieval': {}}
        
        try:
            model = genai.GenerativeModel(model_name=model_choice, tools=[tools_config])
        except Exception as e:
            st.error(f"Error configuring model: {e}")
            st.stop()
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        
        unique_parts = df[part_col].dropna().unique().tolist()
        results_map = {}
        BATCH_SIZE = 3 # Reduced batch size for safety
        
        st.write("--- Debug Log ---")
        
        for i in range(0, len(unique_parts), BATCH_SIZE):
            batch = unique_parts[i:i + BATCH_SIZE]
            status_box.text(f"Processing batch {i//BATCH_SIZE + 1}...")
            
            prompt = f"""
            Find the OEM (Manufacturer) for these specific part numbers: {', '.join(map(str, batch))}.
            Return ONLY the Company Names separated by a pipe symbol (|).
            Example output format: Siemens | Allen-Bradley | Unknown
            """
            
            try:
                response = model.generate_content(prompt)
                
                # --- DEBUG PRINTS (Look at these!) ---
                st.write(f"**Batch Input:** {batch}")
                if response.candidates and response.candidates[0].content:
                     raw_text = response.text
                     st.caption(f"Raw AI Output: {raw_text}") # Shows exactly what AI replied
                     
                     clean_text = raw_text.strip()
                     batch_results = [x.strip() for x in clean_text.split('|')]
                     
                     if len(batch_results) != len(batch):
                         st.warning(f"⚠️ Mismatch! Sent {len(batch)} parts, got {len(batch_results)} answers.")
                         # Pad the list to prevent crash
                         while len(batch_results) < len(batch):
                             batch_results.append("Error: Count Mismatch")
                     
                     for part, res in zip(batch, batch_results):
                         results_map[part] = res
                else:
                    st.error("AI returned no content (blocked?).")
                    for part in batch: results_map[part] = "Error: No Content"

            except Exception as e:
                st.error(f"🛑 CRITICAL ERROR on this batch: {str(e)}")
                for part in batch: results_map[part] = f"Error: {str(e)}"
            
            progress_bar.progress(min((i + BATCH_SIZE) / len(unique_parts), 1.0))
            time.sleep(2)
            
        df['Identified_OEM'] = df[part_col].map(results_map)
        st.success("Done.")
        st.dataframe(df, use_container_width=True)
