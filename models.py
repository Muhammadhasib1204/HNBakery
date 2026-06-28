import os
import mysql.connector

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQLHOST"),
            port=int(os.getenv("MYSQLPORT")),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE")
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error Koneksi: {err}")
        return None