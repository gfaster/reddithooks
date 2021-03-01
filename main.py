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

def get_waits(conn):
    query = "SELECT * FROM waits"
    c = conn.cursor()
    c.execute(query)
    rows = c.fetchall()
    # out = tuple((x[1] for x in rows))
    return rows

def create_tables(conn):
    query1 = """ CREATE TABLE IF NOT EXISTS previous (
                                        id integer PRIMARY KEY,
                                        reddit_id text NOT NULL,
                                        media_lnk text,
                                        date_sent text
                                    ); """

    query2 = """ CREATE TABLE IF NOT EXISTS waits (
                                        id integer PRIMARY KEY,
                                        count integer,
                                        initial integer
                                    ); """


    if conn is None:
        raise ("conn is None in table creation")

    try:
        c = conn.cursor()
        c.execute(query1)

        c = conn.cursor()
        c.execute(query2)
    except:
        print("Table creation error")
        sys.exit(1)

    rows = []
    try:
        rows = get_waits(conn)
    except:
        print("wait rows get error")


    if not len(rows) == len(config["run_wait"]):
        c = conn.cursor()
        c.execute("DELETE FROM waits")
        conn.commit()
        for i in config["run_wait"]:
            c = conn.cursor()
            c.execute("INSERT INTO waits(count, initial) VALUES(1, ?)", (i,))
        conn.commit()
    print("table init finished.")

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

def decrement_waits(conn):
    print("decrimenting")
    current = get_waits(conn)
    for i in current:
        c = conn.cursor()
        if i[1] == 1:
            c.execute("UPDATE waits SET count = ? WHERE id = ?", (i[2], i[0]))
            print("resetting")
        else:
            c.execute("UPDATE waits SET count = ? WHERE id = ?", (i[1] - 1, i[0]))
            print("decrimenting")
    conn.commit()

def verify_timing(conn, hook_index):
    initial = config["run_wait"]
    current = get_waits(conn)
    out = current[hook_index][1] == 1
    print (f"verified the timing on {hook_index}, {out}")
    return out

def get_image_from_entry(entry):
    content = entry['content'][0]['value']
    img = re.findall(r'href="(.*?)"', content)[2]
    if ".jpg" not in img and ".png" not in img:
        print(f"Incorrect format: {img}")
        raise Exception(f"Incorrect format: {img}")

    return img
	
def get_id_from_entry(entry):
    return entry["id"].split(r"/")[-1]

def send(conn, media_lnk):

    payload_data = dict()
    

    
    payload_data["embeds"] = [{"image": {"url": media_lnk}}]
    print("sending...")
    for i in range(len(config["webhooks"])):
        hook = config["webhooks"][i]
        if not verify_timing(conn, i):
            print(f"not yet for {i}")
            continue
        payload_data["content"] = random.choice(config["quips"])
        x = requests.post(hook, json = payload_data)
        print(x)
        time.sleep(config["request_pause"])





def main():
    print("starting...")
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
            send(conn, media_lnk)
            
            add_post(conn, entry_id, media_lnk)
            
            decrement_waits(conn)
            
            print(f"Just sent {media_lnk}!")
            complete = True
            
        except:
            continue

        if complete:
            sys.exit(0)

        print("didn't find anything new :(")

    sys.exit(1)

    

main()



