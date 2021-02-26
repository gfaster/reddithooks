import feedparser
import requests
import json
import re
import sqlite3
from datetime import datetime
import sys
import time
import random

with open("config.json") as config_file:
	config = json.load(config_file)

d = feedparser.parse(config["feed"])



def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except:
        print("Connection creation error")

    return conn

def create_tables(conn):
    query = """ CREATE TABLE IF NOT EXISTS previous (
                                        id integer PRIMARY KEY,
                                        reddit_id text NOT NULL,
                                        media_lnk text,
                                        date_sent text
                                    ); """

    if conn is None:
        raise ("conn is None in table creation")

    try:
        c = conn.cursor()
        c.execute(query)
        
    except:
        print("Table creation error")

    # query_count += 1

def verify_unique(conn, reddit_id):
    query = "SELECT * FROM previous WHERE reddit_id=?;"
    cur = conn.cursor()
    cur.execute(query, (reddit_id,))
    # cur.execute("SELECT * FROM previous")
    rows = cur.fetchall()
    # query_count += 1

    for row in rows:
        raise Exception(f"{reddit_id} is not unique")
    else:
        return True

def add_post(conn, reddit_id, media_lnk):
    query  = '''INSERT INTO previous(reddit_id,media_lnk,date_sent)
                VALUES(?,?,?) '''

    date = datetime.now().strftime("%F")

    cur = conn.cursor()
    cur.execute(query, (reddit_id, media_lnk, date))
    conn.commit()
    # query_count += 1

    return cur.lastrowid

def get_image_from_entry(entry):
    content = entry['content'][0]['value']
    img = re.findall(r'href="(.*?)"', content)[2]
    if ".jpg" not in img and ".png" not in img:
        raise Exception(f"Incorrect format: {img}")

    return img
	

def get_id_from_entry(entry):
    return entry["id"].split(r"/")[-1]


def send(media_lnk, message="Here is an image!"):

    payload_data = dict()
    

    
    payload_data["embeds"] = [{"image": {"url": media_lnk}}]

    for hook in config["webhooks"]:
        payload_data["content"] = random.choice(config["quips"])
        x = requests.post(hook, json = payload_data)
        print(x)
        time.sleep(config["request_pause"])





def main():
    query_count = 0
    request_count = 0   

    conn = create_connection(config["db_file"])
    create_tables(conn)

    for entry in d["entries"]:

        complete = False
        
        try:   
            entry_id = get_id_from_entry(entry)
            verify_unique(conn, entry_id)
            media_lnk = get_image_from_entry(entry)
            add_post(conn, entry_id, media_lnk)
            send(media_lnk)
            
            print(f"Just sent {media_lnk}!")
            complete = True
            
        except:
            continue

        if complete:
            sys.exit(0)

        print("didn't find anything new :(")

    sys.exit(1)

    

main()



