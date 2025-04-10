import os
from typing import Dict, List, Any
from langchain_core.messages import AIMessage, HumanMessage


def format_chat_history(messages: List[Dict[str, str]]) -> List:
    """
    Format chat history from Streamlit format to LangChain format

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys

    Returns:
        List of LangChain message objects
    """
    chat_history = []
    for msg in messages:
        if msg["role"] == "user":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            chat_history.append(AIMessage(content=msg["content"]))
    return chat_history


def configure_environment(openai_key: str = None, pinecone_key: str = None,
                          pinecone_index: str = None) -> Dict[str, bool]:
    """
    Configure environment variables for API keys

    Args:
        openai_key: OpenAI API key
        pinecone_key: Pinecone API key
        pinecone_index: Pinecone index name

    Returns:
        Dictionary indicating which keys were set
    """
    result = {"openai": False, "pinecone": False, "index": False}

    if openai_key and openai_key.strip():
        os.environ["OPENAI_API_KEY"] = openai_key
        result["openai"] = True

    if pinecone_key and pinecone_key.strip():
        os.environ["PINECONE_API_KEY"] = pinecone_key
        result["pinecone"] = True

    if pinecone_index and pinecone_index.strip():
        os.environ["PINECONE_INDEX"] = pinecone_index
        result["index"] = True

    return result


def get_url_domain(url: str) -> str:
    """
    Extract domain from URL

    Args:
        url: Full URL

    Returns:
        Domain name
    """
    from urllib.parse import urlparse

    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        return domain
    except:
        return url


def chunk_stats(json_data: List[Dict]) -> Dict[str, Any]:
    """
    Generate statistics about the chunks

    Args:
        json_data: List of chunk dictionaries

    Returns:
        Dictionary with statistics
    """
    if not json_data:
        return {"count": 0}

    # Count chunks
    chunk_count = len(json_data)

    # Get unique URLs
    urls = set()
    domains = set()
    total_length = 0

    for chunk in json_data:
        url = chunk.get("url", "")
        if url:
            urls.add(url)
            domains.add(get_url_domain(url))

        # Track content length
        content_length = chunk.get("chunk_length", 0)
        if not content_length and "content" in chunk:
            content_length = len(chunk["content"])
        total_length += content_length

    return {
        "count": chunk_count,
        "unique_urls": len(urls),
        "unique_domains": len(domains),
        "domains": list(domains),
        "total_content_length": total_length,
        "avg_chunk_length": total_length / chunk_count if chunk_count else 0
    }
