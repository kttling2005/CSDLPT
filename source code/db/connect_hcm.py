import mysql.connector
from config import DB_CONFIG

def get_hcm_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["hcm"]["host"],
        port=DB_CONFIG["hcm"]["port"],
        user=DB_CONFIG["hcm"]["user"],
        password=DB_CONFIG["hcm"]["password"],
        database=DB_CONFIG["hcm"]["database"]
    )