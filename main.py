import feedparser
import requests
import json
import re
import sqlite3

with open("config.json") as config_file:
	config = json.load(config_file)
d = feedparser.parse(config["feed"])


def create_connection(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(sqlite3.version)
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def get_image_from_entry(entry):
	content = entry['content'][0]['value']
	img = re.findall(r'href="(.*?)"', content)
	return img[2]



payload_data = dict()
i = 0
entry = get_image_from_entry(d['entries'][0])


if ".jpg" not in entry and ".png" not in entry:
	pass
else:
	payload_data["content"] = "Here is an image!"
	payload_data["embeds"] = [{"image": {"url": entry}}]

x = requests.post(config["webhooks"][0], json = payload_data)
exit()