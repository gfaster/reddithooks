import feedparser
import requests
import json
import re
from datetime import datetime
import sys
import time
import random
from databases import Database
import asyncio

with open("config.json") as config_file:
	config = json.load(config_file)



hook_num = len(config["webhooks"])

query_count = 0
DEBUG = False


def gprint(message):
	if DEBUG:
		print(message)



database = Database(f'sqlite:///{config["db_file"]}')


# timing different calls
timer = 0
def timer_start():
	global timer
	timer = time.time()
def timer_end():
	return time.time() - timer

timer_start()
asyncio.run(database.connect())
gprint("Database init took %3.2f"%(timer_end()))

timer_start()
d = feedparser.parse(config["feed"])
gprint("Feed fetch took %3.2f"%(timer_end()))




wait_cache = []
async def get_waits():
	global wait_cache
	global query_count

	if wait_cache:
		return wait_cache

	
	query = "SELECT * FROM waits"
	rows = await database.fetch_all(query=query)
	query_count += 1
	wait_cache = rows
	# out = tuple((x[1] for x in rows))
	return rows

async def create_tables():
	global query_count
	timer_start()
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



	try:
		await database.execute(query=query1)
		query_count += 1

		await database.execute(query=query2)
		query_count += 1

	except Exception as e:
		gprint(f"Table creation error: {e}")
		sys.exit(1)

	rows = []
	try:
		rows = await get_waits()
	except:
		gprint("wait rows get error")


	if not len(rows) == len(config["run_wait"]):
		await database.execute("DELETE FROM waits")
		query_count += 1
		for i in config["run_wait"]:
			await database.execute(query="INSERT INTO waits(count, initial) VALUES(1, :initial)", values={'initial':i})
			query_count += 1
	gprint("table init finished in %3.2f" %(timer_end()))

unq_cached_hook = -1
unq_cache = []
async def verify_unique(reddit_id, hook_id):
	global query_count
	global unq_cache
	global unq_cached_hook

	if unq_cached_hook != hook_id:

		# this should always work - I believe reddit rss has no more than 25 entries
		# since the order is id DESC, it grabs the most recent several
		# if there is any duplicates, this line is the culprit
		query = "SELECT reddit_id FROM previous WHERE hook_id=:hook_id ORDER BY id DESC LIMIT 200;"
		unq_cache = await database.fetch_all(query=query, values={'hook_id': hook_id})

		unq_cached_hook = hook_id

		query_count += 1


	# sqlite fetch returns tuples, so we need to search the tuples
	if (reddit_id,) in unq_cache:
		gprint(f"{reddit_id} is not unique for hook {hook_id}")
		raise Exception(f"{reddit_id} is not unique for hook {hook_id}")
	else:
		return True

async def add_post(reddit_id, media_lnk, hook_id):
	global query_count
	query  = '''INSERT INTO previous(reddit_id,media_lnk,date_sent,hook_id)
				VALUES(:reddit_id,:media_lnk,:date_sent,:hook_id) '''

	date = datetime.now().strftime("%F")

	await database.execute(query=query, values={'reddit_id': reddit_id, 'media_lnk':media_lnk, 'date_sent':date, 'hook_id':hook_id})
	query_count += 1

	return None

async def decrement_waits():
	global query_count
	current = await get_waits()
	for i in current:

		if i[2] == 1:
			continue

		if i[1] == 1:
			await database.execute(query="UPDATE waits SET count = :count WHERE id = :id", values={'count':i[2], 'id':i[0]})
			gprint(f"resetting id {i[0] - 1}")
		else:
			await database.execute(query="UPDATE waits SET count = :count WHERE id = :id", values={'count':i[1] - 1, 'id':i[0]})
		query_count += 1

async def verify_timing(hook_index):
	# the "run_wait" setting means that we only want to send to the webhook corresponding to the index 
	# every that many times the program is run 
	initial = config["run_wait"]
	current = await get_waits()
	out = current[hook_index][1] == 1
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
	timer_start()
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
	gprint("Sent image to webhook %i in %3.2f" %(hook_index, timer_end()))

async def find_entry(hook_id):
	for entry in d["entries"]:

		# I'm not sure what I think of this here - it will be called again after this function
		# do I want to avoid that?
		entry_id = get_id_from_entry(entry)
		
		try:
			await verify_unique(entry_id, hook_id)
			get_image_from_entry(entry)
		except Exception as e:
			gprint(str(e))
			continue

		return entry

	raise Exception(f"couldn't find any unique posts for hook {hook_id}")

class gcolor:
	NUMBER = '\033[92m'
	ENDC = '\033[0m'
	FAIL = '\033[91m'



async def main():


	await create_tables()

	complete = [False] * hook_num

	for i in range(hook_num):

		# don't bother finding a post to send if it's not time
		if not await verify_timing(i):
			continue

		try:
			entry = await find_entry(i)
			entry_id = get_id_from_entry(entry)
			media_lnk = get_image_from_entry(entry)

			send(media_lnk, i)

			await add_post(entry_id, media_lnk, i)

		except Exception as e: print(f"{gcolor.FAIL}POST FAILURE: {e}{gcolor.ENDC}")

	try:
		await decrement_waits()
	except Exception as e: print(f"{gcolor.FAIL}Decriment failure: {e}\n\tThis will cause unsatisfactory post volumes{gcolor.ENDC}")

	print(f"finished having made {gcolor.NUMBER}{query_count}{gcolor.ENDC} queries in total")



	

asyncio.run(main())



