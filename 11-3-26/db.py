"""Connect the desk to its MySQL database"""

import os
import mysql.connector

def connect():
    """Returns a connection object to ticket_desk at the root account"""
    return mysql.connector.connect(
        host="127.0.0.1",
        port="3306",
        user="root",
        password=os.environ["DESK_DB_PASSWORD"],
        database="ticket_desk"
    )