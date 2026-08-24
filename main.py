from src.load_data import load_data_to_db


import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
)

file_path = "data/10K.pdf"

if __name__ == "__main__":
    load_data_to_db(file_path, clear_flag=True)