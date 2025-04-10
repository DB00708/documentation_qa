#!/usr/bin/env python3
import os
import asyncio
from rag.docbot import DocBot
from dotenv import load_dotenv
from utils.logger import setup_logger
from flask import Flask, request, jsonify
from knowledge_base import KnowledgeBaseGenerator


load_dotenv()

app = Flask(__name__)
logger = setup_logger(log_dir=os.environ.get('LOG_DIR', './logs'))


# Initialize DocBot with environment variables or default values
def get_docbot():
    """Create and return a DocBot instance with configured credentials."""
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    pinecone_api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX", "docbot-index")

    return DocBot(
        index_name=index_name,
        openai_api_key=openai_api_key,
        pinecone_api_key=pinecone_api_key
    )


@app.route('/store-documents', methods=['POST'])
def store_documents():
    """
    API endpoint to store document chunks in the vector database.

    Request JSON format:
    {
        "documents": [
            {
                "content": "Document content text",
                "url": "https://source-url.com/path",
                "chunk_length": 500
            },
            ...
        ],
        "namespace": "optional-namespace"
    }

    Returns:
        JSON with status and document count
    """
    # Get JSON payload
    payload = request.json

    # Validate request
    if not payload or 'documents' not in payload:
        logger.error("Missing 'documents' key in request payload")
        return jsonify({
            'status': 'error',
            'message': 'Please provide documents in the request body'
        }), 400

    namespace = payload.get('namespace')
    documents = payload['documents']

    # Initialize DocBot
    try:
        docbot = get_docbot()
    except Exception as e:
        logger.error(f"Error initializing DocBot: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error initializing document store: {str(e)}'
        }), 500

    # Store documents
    try:
        logger.info(f"Storing {len(documents)} documents" +
                    (f" in namespace: {namespace}" if namespace else ""))

        result = docbot.load_json_data(documents, namespace)
        logger.info(f"Documents stored successfully: {result['document_count']} documents")

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error storing documents: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error storing documents: {str(e)}'
        }), 500


@app.route('/query', methods=['POST'])
def query():
    """
    API endpoint to query the document database and get responses.

    Request JSON format:
    {
        "query": "User's question text",
        "chat_history": [optional array of previous messages],
        "metadata_filter": {optional filter criteria}
    }

    Returns:
        JSON with response text
    """
    # Get JSON payload
    payload = request.json

    # Validate request
    if not payload or 'query' not in payload:
        logger.error("Missing 'query' key in request payload")
        return jsonify({
            'status': 'error',
            'message': 'Please provide a query in the request body'
        }), 400

    query_text = payload['query']
    chat_history = payload.get('chat_history', [])
    metadata_filter = payload.get('metadata_filter')

    # Initialize DocBot
    try:
        docbot = get_docbot()
    except Exception as e:
        logger.error(f"Error initializing DocBot: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error initializing query engine: {str(e)}'
        }), 500

    # Generate response
    try:
        logger.info(f"Processing query: {query_text}")
        response = docbot.query(query_text, chat_history, metadata_filter)
        logger.info("Response generated successfully")

        return jsonify({
            'status': 'success',
            'response': response
        })
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating response: {str(e)}'
        }), 500


@app.route('/generate', methods=['POST'])
async def generate_knowledge_base():
    # Get parameters from JSON payload
    payload = request.json

    # Extract parameters with defaults if not provided
    url = payload.get('url', '')
    if not url:
        return jsonify({
            'status': 'bad request',
            'message': 'Please provide a url of the documentation page'
        }), 400

    depth = payload.get('depth', 2)
    output_dir = payload.get('output_dir', './docs_content')
    concurrency = payload.get('concurrency', 5)
    log_dir = payload.get('log_dir', './logs')

    # Set up logging
    logger = setup_logger(log_dir=log_dir)

    # Create knowledge base generator
    generator = KnowledgeBaseGenerator(
        output_dir=output_dir,
        max_depth=depth,
        concurrency=concurrency
    )

    # Generate knowledge base
    try:
        consolidated_path = await generator.generate(url)
        logger.info(f"Knowledge base generation complete: {consolidated_path}")
        return jsonify({
            'status': 'success',
            'output_path': consolidated_path
        })
    except Exception as e:
        logger.error(f"Error generating knowledge base: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/generate-sync', methods=['POST'])
def generate_knowledge_base_sync():
    return asyncio.run(generate_knowledge_base())


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        'status': 'ok',
        'service': 'docbot-api'
    })


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
