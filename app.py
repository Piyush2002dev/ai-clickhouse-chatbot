import streamlit as st
import pandas as pd
import base64
import traceback
import io
from utils import create_conversational_chain

def format_and_display_response(response):
    """Converts any type of response into a structured table format."""
    if not response:
        st.warning("No data available.")
        return

    if isinstance(response, list):
        if isinstance(response[0], tuple):
            df = pd.DataFrame(response)
        elif isinstance(response[0], dict):
            df = pd.DataFrame(response)
        else:
            df = pd.DataFrame({'Response': response})
    elif isinstance(response, dict):
        df = pd.DataFrame([response])
    else:
        df = pd.DataFrame({'Response': [response]})

    st.dataframe(df)
    st.session_state['export_data'] = df

def export_to_excel():
    """Exports the data to an Excel file and provides a download button."""
    if 'export_data' in st.session_state:
        df = st.session_state['export_data']
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0)
        b64 = base64.b64encode(output.read()).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="query_results.xlsx">Download Excel File</a>'
        st.sidebar.markdown(href, unsafe_allow_html=True)

def main():
    """Main function for the Streamlit chatbot app."""
    st.set_page_config(page_title="AI Chatbot", layout="wide")

    # Sidebar Configuration
    st.sidebar.title("Settings")
    st.sidebar.info("Connecting to the database and initializing the AI model...")

    try:
        db_chain, chain = create_conversational_chain()
        st.sidebar.success("Connected Successfully!")
    except Exception as e:
        st.sidebar.error(f"Connection failed: {str(e)}")
        return

    # Load chatbot image
    if "chatbot_image" not in st.session_state:
        with open("195.png", "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode()
            st.session_state["chatbot_image"] = encoded_image

    # Chatbot Header with Image
    st.markdown(f"""
        <div style='text-align: center;'>
            <img src='data:image/png;base64,{st.session_state["chatbot_image"]}' width='150'/>
            <h1 style='color: #4CAF50;'>AI-Powered Chatbot for Clickhouse</h1>
            <p>Ask me anything, and I'll do my best to help!</p>
        </div>
        <hr>
    """, unsafe_allow_html=True)

    # Chat history initialization
    if "history" not in st.session_state:
        st.session_state["history"] = []

    # Chat Display Section
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state["history"]:
            align = "right" if "You:" in msg else "left"
            bg_color = "#d9f1ff" if "You:" in msg else "#e0f7da"

            st.markdown(f"""
                <div style='text-align: {align}; padding: 10px; background: {bg_color}; 
                border-radius: 10px; margin: 5px 0; color: #000000; font-weight: bold;'>
                    {msg}
                </div>
            """, unsafe_allow_html=True)

    # User Input Section
    user_input = st.text_area("Type your message here:", key="user_input")

    col1, col2 = st.columns([0.8, 0.2])

    with col2:
        submit_button = st.button("Send")  # Fixed submit_button issue

    # **Fix: Ensure correct indentation**
    if submit_button and user_input.strip():
        with st.spinner("Thinking..."):
            try:
                response = db_chain.run(user_input)
                st.session_state["history"].append(f"**You:** {user_input}")

                if isinstance(response, (list, tuple, dict)) and response:
                    st.session_state["history"].append("**Bot:** (See table below)")
                    format_and_display_response(response)
                else:
                    st.session_state["history"].append(f"**Bot:** {response or 'No data found'}")

            except Exception as e:
                error_message = f"❌ Error: {str(e)}"
                error_traceback = traceback.format_exc()
                st.session_state["history"].append(f"**Bot:** {error_message}")

                st.error(error_message)
                with st.expander("Show Error Details"):
                    st.code(error_traceback, language="python")

                # Log error to a file
                with open("error_log.txt", "a") as log_file:
                    log_file.write(f"\n{error_traceback}\n")

        st.rerun()

    # Clear Chat Button
    if st.sidebar.button("Clear Chat"):
        st.session_state["history"] = []
        st.rerun()
    
    # Export Button in Sidebar
    export_to_excel()

if __name__ == "__main__":
    main()
