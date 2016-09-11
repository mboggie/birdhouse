# -*- coding: utf-8 -*-
# May or may not need that up there, just saving it so I know what to do if I ever need unicode or something crazy.
# Note: Refactoring to use the better-maintained Python Twitter Tools APIs and hooks (https://github.com/sixohsix/twitter)

from twython import Twython, TwythonAuthError
from datetime import datetime as dt, timedelta
from dateutil.parser import parse
from dateutil.tz import tzlocal
import os, sys, json, time, string, re
import urllib, httplib, base64
import beanstalkc
import redis
import argparse
import ConfigParser
import logging

# Default TTL = how long an #SD tweet lasts if no number of minutes has been specified
DEFAULT_TTL = 5
DEFAULT_SINCE_ID = 240859602684612608 #random, yet valid, id from 2012. Twitter doesn't like it if you just pass 0.

# setup logging
logger = logging.getLogger("birdhouse")
logger.setLevel(logging.INFO)
FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=FORMAT)

# parse arguments
argparser = argparse.ArgumentParser()
argparser.add_argument('config', help='path to config file')
args = argparser.parse_args()

# read application config
cfg = ConfigParser.ConfigParser()
cfg.read(args.config)

try:

    CONSUMER_KEY = cfg.get('twitter', 'app_key')
    CONSUMER_SECRET = cfg.get('twitter', 'app_secret')
    # BEANSTALK_HOST = cfg.get('beanstalk', 'host')
    # BEANSTALK_PORT = int(cfg.get('beanstalk', 'port'))
    # BEANSTALK_TUBE = cfg.get('beanstalk', 'tube')
    REDIS_HOST = cfg.get('redis', 'host')
    REDIS_PORT = int(cfg.get('redis', 'port'))

except:
	logger.critical("Please set your config variables properly in %s before running birdhouse-mon.py." %args.config)
	sys.exit(2)

#connect to beanstalk queue
# beanstalk = beanstalkc.Connection(host=BEANSTALK_HOST, port=BEANSTALK_PORT)
# beanstalk.connect()
#
# # use tube to place tweets for destruction
# beanstalk.use(BEANSTALK_TUBE)

#connect to redis
rserver = redis.Redis(REDIS_HOST, REDIS_PORT)

def processAuthor(userobj):
	# stores user id number, handle, and name in redis.
	# NOTE: when using this information, validate that the handle/name
	# haven't changed since this was stored, and if possible, update them.
	rserver.hmset("author:"+userobj['id_str'], {"screen_name":userobj['screen_name'], "name":userobj['name']})
	return

def processTweet(tweet, follower):
	# stores lightweight tweet in redis. id_str, text, and attachments
	rserver.hmset("tweet:"+tweet['id_str'], {"user":follower, "author":tweet['user']['id_str'], "entities":json.dumps(tweet['entities']), "text": tweet['text']})
	return

if __name__ == "__main__":

	logger.info("Executing twitter stream monitor")

	#get list of subscribers
	userlist = rserver.lrange("users", 0, -1)
	logger.debug(userlist)

	#begin loop
	for id_str in userlist:
		logger.debug("Checking timeline for user %s"%id_str)
		#in this area, add try/except areas for db calls and for Twitter info
		since_id = rserver.get("since_id:"+id_str)
		if since_id is None:
			since_id = DEFAULT_SINCE_ID
		else:
			since_id = long(since_id)
		creds = rserver.get("credentials:"+id_str)
		if creds is None:
			logger.warning("%s has revoked access and has no credentials stored"%id_str)
			rserver.delete("since_id:"+id_str)
			rserver.lrem("users", id_str, 0)
		else:
			creds = json.loads(creds)
			# connect to Twitter with keys for each individual user
			try:
				t = Twython(CONSUMER_KEY, CONSUMER_SECRET, creds["token"], creds["secret"])

				# for each user who has signed up, retrieve all tweets in their timeline since last we checked
				# TODO: Alter this to test for the kind of search we're running (list, timeline, or special)
				tweets =t.get_home_timeline(since_id=since_id)
				logger.debug("%d tweets received for %s" % (len(tweets), id_str))

				for tweet in tweets:

					# save the user in a separate structure
					processAuthor(tweet['user'])
					# save the tweet with its follower source (with the user data stripped to simplify things)
					processTweet(tweet, id_str)
					#	reset this user's pointer so future calls don't return tweets we've already seen
					if tweet['id'] > since_id:
						rserver.set("since_id:"+id_str, tweet['id'])
						since_id = tweet['id']
						logger.debug("setting since_id to " + str(tweet['id']))
						#end inner for

			except TwythonAuthError:
				# user has revoked access; mark them as disabled and move on
				logger.warning("%s has revoked access; removing records"%id_str)
				rserver.delete("credentials:"+id_str)
				rserver.delete("since_id:"+id_str)
				rserver.lrem("users", id_str, 0)
	#end outer for
#end
