import os
import logging
from datetime import datetime


def setup_logger(log_dir="logs"):
    """
    Set up a logger with both file and console handlers.

    Args:
        log_dir: Directory to store log files

    Returns:
        Configured logger
    """
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{timestamp}.log")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger("docbot")
    return logger


# Create a default logger
logger = setup_logger()
