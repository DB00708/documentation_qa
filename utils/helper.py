import json
from typing import Any
from urllib.parse import urlparse


def clean_url(url):
    parsed = urlparse(url)
    cleaned = parsed.netloc.replace('.', '_')
    return cleaned


def read_documentation_file(file_path: str) -> str:
    """Read the documentation from a text file.

    Args:
        file_path: Path to the text file containing the documentation.

    Returns:
        The content of the documentation
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        raise Exception(f"Error reading documentation file: {e}")


def load_json_file(file_path: str) -> Any:
    """
    Load and parse a JSON file

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON content
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(data: Any, file_path: str) -> None:
    """
    Save data to a JSON file

    Args:
        data: Data to save
        file_path: Path where to save the JSON file
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
