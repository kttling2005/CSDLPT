import mysql.connector
from config import DB_CONFIG

def get_hn_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["hn"]["host"],
        port=DB_CONFIG["hn"]["port"],
        user=DB_CONFIG["hn"]["user"],
        password=DB_CONFIG["hn"]["password"],
        database=DB_CONFIG["hn"]["database"]
    )