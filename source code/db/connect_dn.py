import mysql.connector
from config import DB_CONFIG

def get_dn_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["dn"]["host"],
        port=DB_CONFIG["dn"]["port"],
        user=DB_CONFIG["dn"]["user"],
        password=DB_CONFIG["dn"]["password"],
        database=DB_CONFIG["dn"]["database"]
    )