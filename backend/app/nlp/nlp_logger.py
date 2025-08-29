import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler("../nlp.log")
file_handler.setLevel(logging.DEBUG)  # Logs all levels to file
console_handler = logging.StreamHandler()
console_handler.setLevel(
    logging.INFO
)  # Only logs INFO, WARNING, ERROR, CRITICAL to console

file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")

file_handler.setFormatter(file_formatter)
console_handler.setFormatter(console_formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
