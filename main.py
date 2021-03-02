import feedparser
import requests
import json
import re
import sqlite3
from datetime import datetime
import sys
import time
import random
import colorama

with open("config.json") as config_file:
	config = json.load(config_file)

d = feedparser.parse(config["feed"])
hook_num = len(config["webhooks"])

query_count = 0
DEBUG = False


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
    except Exception as e:
        raise Exception(f"Connection creation error: {e}")

    return conn

def get_waits(conn):
    global query_count
    query = "SELECT * FROM waits"
    c = conn.cursor()
    c.execute(query)
    rows = c.fetchall()
    query_count += 1
    # out = tuple((x[1] for x in rows))
    return rows

def create_tables(conn):
    global query_count
    query1 = """ CREATE TABLE IF NOT EXISTS previous (
                                        id integer PRIMARY KEY,
                                        reddit_id text NOT NULL,
                                        media_lnk text,
                                        date_sent text,
                                        hook_id text
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
        query_count += 1

        c = conn.cursor()
        c.execute(query2)
        query_count += 1

    except Exception as e:
        gprint(f"Table creation error: {e}")
        sys.exit(1)

    rows = []
    try:
        rows = get_waits(conn)
    except:
        gprint("wait rows get error")


    if not len(rows) == len(config["run_wait"]):
        c = conn.cursor()
        c.execute("DELETE FROM waits")
        conn.commit()
        query_count += 1
        for i in config["run_wait"]:
            c = conn.cursor()
            c.execute("INSERT INTO waits(count, initial) VALUES(1, ?)", (i,))
            query_count += 1
        conn.commit()
    gprint("table init finished.")

    # query_count += 1

def verify_unique(conn, reddit_id, hook_id):
    global query_count
    query = "SELECT * FROM previous WHERE (reddit_id=? AND hook_id=?);"
    cur = conn.cursor()
    cur.execute(query, (reddit_id,hook_id))
    rows = cur.fetchall()
    query_count += 1

    for row in rows:
        raise Exception(f"{reddit_id} is not unique for hook {hook_id}")
    else:
        return True

def add_post(conn, reddit_id, media_lnk, hook_id):
    global query_count
    query  = '''INSERT INTO previous(reddit_id,media_lnk,date_sent,hook_id)
                VALUES(?,?,?,?) '''

    date = datetime.now().strftime("%F")

    cur = conn.cursor()
    cur.execute(query, (reddit_id, media_lnk, date, hook_id))
    conn.commit()
    query_count += 1

    return cur.lastrowid

def decrement_waits(conn):
    global query_count
    current = get_waits(conn)
    for i in current:
        c = conn.cursor()
        if i[1] == 1:
            c.execute("UPDATE waits SET count = ? WHERE id = ?", (i[2], i[0]))
            gprint(f"resetting id {i[0] - 1}")
        else:
            c.execute("UPDATE waits SET count = ? WHERE id = ?", (i[1] - 1, i[0]))
        query_count += 1
    conn.commit()

def verify_timing(conn, hook_index):
    # the "run_wait" setting means that we only want to send to the webhook corresponding to the index 
    # every that many times the program is run 
    initial = config["run_wait"]
    current = get_waits(conn)
    out = current[hook_index][1] == 1
    gprint (f"verified the timing on {hook_index}, {out}")
    return out

def get_entry(index):
    out = d["entries"][index]
    return out

def get_image_from_entry(entry):
    content = entry['content'][0]['value']
    img = re.findall(r'href="(.*?)"', content)[2]
    if ".jpg" not in img and ".png" not in img:
        raise Exception(f"Incorrect format: {img}")

    return img
	
def get_id_from_entry(entry):
    # id refers to the unique id reddit gives to each post
    return entry["id"].split(r"/")[-1]

def send(media_lnk, hook_index):

    payload_data = dict()
    
    hook = config["webhooks"][hook_index]
    payload_data["embeds"] = [{"image": {"url": media_lnk}}]
    payload_data["content"] = random.choice(config["quips"])

    x = requests.post(hook, json = payload_data)

    gprint(x)
    if not x.ok:
        raise Exception(f"request failed ({x.status})")

    # we want to wait after sending a request
    # I'm not sure if I should leave this withing this function or move it out
    time.sleep(config["request_pause"])

def find_entry(conn, hook_id):
    for entry in d["entries"]:

        # I'm not sure what I think of this here - it will be called again after this function
        # do I want to avoid that?
        entry_id = get_id_from_entry(entry)
        
        try:
            verify_unique(conn, entry_id, hook_id)
            get_image_from_entry(entry)
        except Exception:
            continue

        return entry

    raise Exception(f"couldn't find any unique posts for hook {hook_id}")

class gcolor:
    NUMBER = '\033[92m'
    ENDC = '\033[0m'
    FAIL = '\033[91m'

    def init():
        global DEBUG
        if DEBUG:
            gprint("DEBUG ENABLE")
            # gcolor.NUMBER = ''
            # gcolor.ENDC = ''
            # gcolor.FAIL = ''

def gprint(message):
    if DEBUG:
        print(message)


def main():


    conn = create_connection(config["db_file"])
    create_tables(conn)
    colorama.init()

    complete = [False] * hook_num

    for i in range(hook_num):

        # don't bother finding a post to send if it's not time
        if not verify_timing(conn, i):
            continue

        try:
            entry = find_entry(conn, i)
            entry_id = get_id_from_entry(entry)
            media_lnk = get_image_from_entry(entry)

            send(media_lnk, i)

            add_post(conn, entry_id, media_lnk, i)

        except Exception as e: print(f"{gcolor.FAIL}POST FAILURE: {e}{gcolor.ENDC}")

    decrement_waits(conn)

    print(f"finished having made {gcolor.NUMBER}{query_count}{gcolor.ENDC} queries in total")



    
gcolor.init()
main()



