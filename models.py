import mysql.connector

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='hn_bakery_db'
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error Koneksi: {err}")
        return None