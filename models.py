import os
import mysql.connector

def get_db_connection():
    try:
        print("MYSQLHOST =", os.getenv("MYSQLHOST"))
        print("MYSQLPORT =", os.getenv("MYSQLPORT"))
        print("MYSQLUSER =", os.getenv("MYSQLUSER"))
        print("MYSQLDATABASE =", os.getenv("MYSQLDATABASE"))

        conn = mysql.connector.connect(
            host=os.getenv("MYSQLHOST"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(os.getenv("MYSQLPORT"))
        )
        return conn

    except Exception as err:
        print("ERROR:", err)
        return None