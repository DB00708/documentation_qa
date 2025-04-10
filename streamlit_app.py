#!/usr/bin/env python3
import streamlit as st
import requests
import json
import os
import time
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# API endpoints
API_BASE = "http://localhost:5000"
KB_GENERATOR_API = f"{API_BASE}/generate-sync"
STORE_DOCUMENTS_API = f"{API_BASE}/store-documents"
QUERY_API = f"{API_BASE}/query"

# Set page configuration
st.set_page_config(
    page_title="Documentation Assistant",
    page_icon="📚",
    layout="wide"
)

# Custom styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .tab-header {
        font-size: 1.8rem;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .success-message {
        background-color: #D5F5E3;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-message {
        background-color: #FADBD8;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #F0F2F6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1E88E5;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


# Initialize session state
def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "kb_api_keys_set" not in st.session_state:
        st.session_state.kb_api_keys_set = False

    if "chat_api_keys_set" not in st.session_state:
        st.session_state.chat_api_keys_set = False

    if "show_chunk_stats" not in st.session_state:
        st.session_state.show_chunk_stats = False

    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Knowledge Base Generator"

    if "kb_api_config" not in st.session_state:
        st.session_state.kb_api_config = {
            "api_url": KB_GENERATOR_API
        }

    if "chat_api_config" not in st.session_state:
        st.session_state.chat_api_config = {
            "openai_key": os.environ.get("OPENAI_API_KEY", ""),
            "pinecone_key": os.environ.get("PINECONE_API_KEY", ""),
            "pinecone_index": os.environ.get("PINECONE_INDEX", "docbot")
        }


# KB Generator API Configuration
def setup_kb_api_section():
    """Setup API configuration for Knowledge Base Generator"""
    with st.expander("API Configuration", expanded=not st.session_state.kb_api_keys_set):
        # API URL input
        api_url = st.text_input(
            "Knowledge Base Generator API URL",
            value=st.session_state.kb_api_config.get("api_url", KB_GENERATOR_API)
        )

        # Save API config button
        if st.button("Save API Configuration", key="kb_save_api"):
            if api_url:
                # Store in session state
                st.session_state.kb_api_config["api_url"] = api_url
                st.session_state.kb_api_keys_set = True
                st.success("API configuration saved successfully!")
            else:
                st.error("Please provide a valid API URL")


# DocBot API Configuration
def setup_chat_api_keys_section():
    """Setup API keys configuration for DocBot"""
    with st.expander("API Configuration", expanded=not st.session_state.chat_api_keys_set):
        # Get default API keys
        default_openai_key = st.session_state.chat_api_config["openai_key"]
        default_pinecone_key = st.session_state.chat_api_config["pinecone_key"]
        default_pinecone_index = st.session_state.chat_api_config["pinecone_index"]

        # Try to get from secrets if available
        try:
            if not default_openai_key and hasattr(st, "secrets"):
                default_openai_key = st.secrets.get("OPENAI_API_KEY", "")
            if not default_pinecone_key and hasattr(st, "secrets"):
                default_pinecone_key = st.secrets.get("PINECONE_API_KEY", "")
            if hasattr(st, "secrets"):
                default_pinecone_index = st.secrets.get("PINECONE_INDEX", default_pinecone_index)
        except:
            pass

        # API key input fields
        openai_key = st.text_input("OpenAI API Key", value=default_openai_key, type="password", key="chat_openai_key")
        pinecone_key = st.text_input("Pinecone API Key", value=default_pinecone_key, type="password",
                                     key="chat_pinecone_key")
        pinecone_index = st.text_input("Pinecone Index Name", value=default_pinecone_index, key="chat_pinecone_index")

        # API URL input
        api_base = st.text_input(
            "DocBot API Base URL",
            value=API_BASE,
            key="chat_api_base"
        )

        # Save API keys button
        if st.button("Save API Keys", key="chat_save_api"):
            if openai_key and pinecone_key:
                # Store in session state
                st.session_state.chat_api_config["openai_key"] = openai_key
                st.session_state.chat_api_config["pinecone_key"] = pinecone_key
                st.session_state.chat_api_config["pinecone_index"] = pinecone_index
                st.session_state.chat_api_config["api_base"] = api_base

                # Set environment variables (for local development)
                os.environ["OPENAI_API_KEY"] = openai_key
                os.environ["PINECONE_API_KEY"] = pinecone_key
                os.environ["PINECONE_INDEX"] = pinecone_index

                # Update API endpoints with new base URL
                global STORE_DOCUMENTS_API, QUERY_API
                STORE_DOCUMENTS_API = f"{api_base}/store-documents"
                QUERY_API = f"{api_base}/query"

                st.session_state.chat_api_keys_set = True
                st.success("API keys saved successfully!")
            else:
                st.error("Please provide both OpenAI and Pinecone API keys")


# Helper function for analyzing uploaded JSON chunks
def chunk_stats(json_data):
    """Generate statistics for document chunks"""
    if not json_data:
        return {"count": 0, "unique_urls": 0, "avg_chunk_length": 0}

    count = len(json_data)

    # URL analysis
    urls = [item.get("url", "") for item in json_data]
    unique_urls = len(set(urls))

    # Domain analysis
    domains = []
    for url in urls:
        try:
            if url and "//" in url:
                domain = url.split("//")[1].split("/")[0]
                domains.append(domain)
        except:
            pass

    unique_domains = list(set(domains))

    # Content length analysis
    lengths = [len(item.get("content", "")) for item in json_data]
    avg_length = sum(lengths) / max(1, len(lengths))

    return {
        "count": count,
        "unique_urls": unique_urls,
        "domains": unique_domains,
        "avg_chunk_length": avg_length
    }


# Format chat history for API
def format_chat_history(messages):
    """Format the chat messages for the API"""
    formatted = []
    for msg in messages:
        if msg["role"] in ["user", "assistant"]:
            formatted.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    return formatted


# Check API health
def check_api_health(api_url=API_BASE):
    """Check if the API is running"""
    try:
        health_url = f"{api_url}/health"
        response = requests.get(health_url, timeout=2)
        return response.status_code == 200
    except:
        return False


# KB Generator sidebar
def kb_generator_sidebar():
    """Sidebar for Knowledge Base Generator tab"""
    st.title("KB Generator Settings")

    # API configuration
    setup_kb_api_section()

    # API status indicator
    api_url = st.session_state.kb_api_config.get("api_url", KB_GENERATOR_API)
    base_url = "/".join(api_url.split("/")[:-1])  # Extract base URL for health check
    api_status = check_api_health(base_url)
    status_color = "green" if api_status else "red"
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <div style="width: 12px; height: 12px; background-color: {status_color}; 
             border-radius: 50%; margin-right: 8px;"></div>
        <span>API Status: {'Online' if api_status else 'Offline'}</span>
    </div>
    """, unsafe_allow_html=True)

    # About section
    with st.expander("About Knowledge Base Generator"):
        st.write("""
        ### Knowledge Base Generator

        This tool crawls documentation websites to build a structured knowledge base.

        **Features:**
        - Configurable crawl depth and concurrency
        - Extracts and processes content
        - Generates usable knowledge base files

        **How to use:**
        1. Configure the API endpoint
        2. Enter the URL of the documentation site
        3. Set crawl parameters
        4. Generate the knowledge base
        """)


# DocBot Chat sidebar
def docbot_chat_sidebar():
    """Sidebar for DocBot Chat tab"""
    st.title("Documentation Chat Settings")

    # API keys configuration
    setup_chat_api_keys_section()

    # API status indicator
    api_base = st.session_state.chat_api_config.get("api_base", API_BASE)
    api_status = check_api_health(api_base)
    status_color = "green" if api_status else "red"
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <div style="width: 12px; height: 12px; background-color: {status_color}; 
             border-radius: 50%; margin-right: 8px;"></div>
        <span>API Status: {'Online' if api_status else 'Offline'}</span>
    </div>
    """, unsafe_allow_html=True)

    # Clear chat button
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    # About section
    with st.expander("About Documentation Chatbot"):
        st.write("""
        ### Documentation Chatbot

        This tool lets you query your documentation using natural language.

        **Features:**
        - Advanced query processing
        - Neural reranking for better results
        - Conversational context
        - Vector database storage

        **How to use:**
        1. Configure API keys
        2. Load documentation chunks
        3. Ask questions in natural language
        """)


# Knowledge Base Generator Tab
def knowledge_base_generator_tab():
    """UI for the knowledge base generator tab"""
    st.markdown('<h2 class="tab-header">Knowledge Base Generator</h2>', unsafe_allow_html=True)
    st.markdown("Generate a knowledge base by crawling documentation websites")

    # Create a form for user input
    with st.form("kb_generator_form"):
        # Input fields with default values
        url = st.text_input("Documentation URL", value="https://docs.crawl4ai.com/")

        col1, col2 = st.columns(2)
        with col1:
            depth = st.number_input("Crawl Depth (Recommended 2)", min_value=1, max_value=10, value=2)
            concurrency = st.number_input("Max Concurrent Crawlers (Recommended 5)", min_value=1, max_value=20, value=5)

        with col2:
            output_dir = st.text_input("Output Directory", value="./docs_content")
            log_dir = st.text_input("Log Directory", value="./logs")

        # Submit button
        submit_button = st.form_submit_button("Generate Knowledge Base")

    # Handle form submission
    if submit_button:
        api_url = st.session_state.kb_api_config.get("api_url", KB_GENERATOR_API)
        base_url = "/".join(api_url.split("/")[:-1])  # Extract base URL for health check

        # Check API health
        if not check_api_health(base_url):
            st.error(f"⚠️ Could not connect to the API. Make sure the Flask API is running at {base_url}")
            return

        # Prepare the payload
        payload = {
            "url": url,
            "depth": depth,
            "output_dir": output_dir,
            "concurrency": concurrency,
            "log_dir": log_dir
        }

        # Show a spinner while the API is being called
        with st.spinner("Generating knowledge base... This may take a while."):
            try:
                # Make the API request
                start_time = time.time()
                response = requests.post(api_url, json=payload)
                end_time = time.time()

                # Process the response
                if response.status_code == 200:
                    result = response.json()

                    # Display success message
                    st.success("Knowledge Base Generated Successfully!")
                    st.json({
                        "output_path": result.get('output_path'),
                        "time_taken": f"{round(end_time - start_time, 2)} seconds",
                        "status": result.get('status')
                    })

                    # Show a button to open the output directory
                    if os.path.exists(result.get('output_path', '')):
                        if st.button("View Generated Files"):
                            # This will only work if Streamlit is running locally
                            os.system(f"explorer {result.get('output_path')}")
                else:
                    error_message = response.json().get('message', 'Unknown error occurred')
                    st.error(f"Error Generating Knowledge Base: {error_message}")
                    st.code(f"Status Code: {response.status_code}")

            except requests.exceptions.ConnectionError:
                st.error(f"⚠️ Could not connect to the API. Make sure the Flask API is running at {api_url}")
            except Exception as e:
                st.error(f"⚠️ An unexpected error occurred: {str(e)}")


# Document Loader Section
def document_loader_section():
    """UI for loading documents into the vector database"""
    with st.expander("Load Documentation Chunks"):
        st.write("Upload a JSON file with pre-chunked documentation")
        uploaded_file = st.file_uploader("Choose a JSON file", type="json")

        if uploaded_file is not None:
            # Load the JSON data
            try:
                json_data = json.load(uploaded_file)

                # Get chunk statistics
                stats = chunk_stats(json_data)

                # Show basic info
                st.info(f"JSON file contains {stats['count']} chunks from {stats['unique_urls']} unique URLs")

                # Show/hide statistics button
                if st.button("Toggle Statistics Details", key="toggle_stats"):
                    st.session_state.show_chunk_stats = not st.session_state.show_chunk_stats

                # Display statistics if toggle is on
                if st.session_state.show_chunk_stats:
                    st.subheader("Chunk Statistics")

                    # Display summary as metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Chunks", stats['count'])
                    with col2:
                        st.metric("Unique URLs", stats['unique_urls'])
                    with col3:
                        st.metric("Avg. Chunk Length", f"{int(stats['avg_chunk_length'])} chars")

                    # Display domains
                    if stats.get('domains'):
                        st.subheader("Domains")
                        domains_list = ", ".join(stats['domains'][:5])
                        if len(stats['domains']) > 5:
                            domains_list += f" and {len(stats['domains']) - 5} more"
                        st.text(domains_list)

                    # Raw stats in JSON
                    st.json(stats)

                # Namespace option
                namespace = st.text_input("Namespace (optional)", "")

                # Load button
                if st.button("Load Chunks into Vector DB"):
                    if not st.session_state.chat_api_keys_set:
                        st.error("Please configure API keys first")
                    else:
                        # Check API health
                        api_base = st.session_state.chat_api_config.get("api_base", API_BASE)
                        if not check_api_health(api_base):
                            st.error(
                                f"⚠️ Could not connect to the API. Make sure the Flask API is running at {api_base}")
                            return

                        with st.spinner("Loading chunks into vector database..."):
                            try:
                                # Prepare request payload
                                payload = {
                                    "documents": json_data,
                                    "namespace": namespace if namespace else None
                                }

                                # Call the API
                                headers = {
                                    "Content-Type": "application/json",
                                    "X-OpenAI-Key": st.session_state.chat_api_config["openai_key"],
                                    "X-Pinecone-Key": st.session_state.chat_api_config["pinecone_key"],
                                    "X-Pinecone-Index": st.session_state.chat_api_config["pinecone_index"]
                                }

                                store_documents_api = f"{api_base}/store-documents"

                                response = requests.post(
                                    store_documents_api,
                                    json=payload,
                                    headers=headers
                                )

                                # Process response
                                if response.status_code == 200:
                                    result = response.json()
                                    if result["status"] == "success":
                                        st.success(result["message"])
                                    else:
                                        st.error(result["message"])
                                else:
                                    st.error(f"Error: API returned status code {response.status_code}")
                                    if response.content:
                                        st.error(response.json().get("message", "Unknown error"))
                            except Exception as e:
                                st.error(f"Error calling API: {str(e)}")
            except Exception as e:
                st.error(f"Error loading JSON file: {str(e)}")


# Chat interface
def display_chat_interface():
    """Display the chat interface for querying documentation"""
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question about the documentation..."):
        if not st.session_state.chat_api_keys_set:
            st.error("Please configure API keys first")
            return

        # Check API health
        api_base = st.session_state.chat_api_config.get("api_base", API_BASE)
        if not check_api_health(api_base):
            st.error(f"⚠️ Could not connect to the API. Make sure the Flask API is running at {api_base}")
            return

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Format chat history for the API
                    chat_history = format_chat_history(st.session_state.messages[:-1])

                    # Prepare request payload
                    payload = {
                        "query": prompt,
                        "chat_history": chat_history,
                        "metadata_filter": None  # Optional filtering
                    }

                    # Send request to API
                    headers = {
                        "Content-Type": "application/json",
                        "X-OpenAI-Key": st.session_state.chat_api_config["openai_key"],
                        "X-Pinecone-Key": st.session_state.chat_api_config["pinecone_key"],
                        "X-Pinecone-Index": st.session_state.chat_api_config["pinecone_index"]
                    }

                    query_api = f"{api_base}/query"

                    response = requests.post(
                        query_api,
                        json=payload,
                        headers=headers
                    )

                    # Process response
                    if response.status_code == 200:
                        result = response.json()
                        response_text = result.get("response", "Sorry, I couldn't generate a response.")

                        # Display the response
                        st.markdown(response_text)

                        # Add assistant response to chat history
                        st.session_state.messages.append({"role": "assistant", "content": response_text})
                    else:
                        error_msg = f"Error: API returned status {response.status_code}"
                        if response.content:
                            error_msg += f": {response.json().get('message', 'Unknown error')}"
                        st.error(error_msg)

                except Exception as e:
                    st.error(f"Error querying API: {str(e)}")
                    # Add error message to chat for better UX
                    error_response = f"I'm sorry, I encountered an error: {str(e)}"
                    st.markdown(error_response)
                    st.session_state.messages.append({"role": "assistant", "content": error_response})


# Documentation chatbot tab
def documentation_chatbot_tab():
    """UI for the documentation chatbot tab"""
    st.markdown('<h2 class="tab-header">Documentation Chatbot</h2>', unsafe_allow_html=True)
    st.write("Ask questions about your technical documentation")

    # API key check
    if not st.session_state.chat_api_keys_set:
        st.warning("Please configure your API keys in the sidebar to get started")

    # Document loader
    document_loader_section()

    # Display chat interface
    display_chat_interface()


def main():
    """Simplified main function with direct tab rendering"""
    # Initialize session state
    initialize_session_state()

    # Header
    st.markdown('<h1 class="main-header">Documentation Assistant</h1>', unsafe_allow_html=True)

    # Create a radio selection instead of tabs - more reliable in Streamlit
    tab_selection = st.radio(
        "Select Tool",
        ["Knowledge Base Generator", "Documentation Chatbot"],
        horizontal=True,
        label_visibility="collapsed"
    )

    # Update the active tab based on selection
    st.session_state.active_tab = tab_selection

    # Display the appropriate sidebar
    with st.sidebar:
        if tab_selection == "Knowledge Base Generator":
            st.title("KB Generator Settings")
            kb_generator_sidebar()
        else:
            st.title("Documentation Chat Settings")
            docbot_chat_sidebar()

    # Render the appropriate content
    if tab_selection == "Knowledge Base Generator":
        knowledge_base_generator_tab()
    else:
        documentation_chatbot_tab()


# Use this as your main function at the bottom of your file
if __name__ == "__main__":
    main()
