import mysql.connector
from config import DB_CONFIG

def get_center_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["center"]["host"],
        port=DB_CONFIG["center"]["port"],
        user=DB_CONFIG["center"]["user"],
        password=DB_CONFIG["center"]["password"],
        database=DB_CONFIG["center"]["database"]
    )