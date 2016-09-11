# -*- coding: utf-8 -*-
from twython import Twython, TwythonAuthError
from datetime import datetime as dt, timedelta
from dateutil.parser import parse
import os, sys, json, time, string, re
import urllib, httplib, base64
import beanstalkc
import redis
import argparse
import ConfigParser
import logging

# setup logging
logger = logging.getLogger("selfdestruct")
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
    BEANSTALK_HOST = cfg.get('beanstalk', 'host')
    BEANSTALK_PORT = int(cfg.get('beanstalk', 'port'))
    BEANSTALK_TUBE = cfg.get('beanstalk', 'tube')
    REDIS_HOST = cfg.get('redis', 'host')
    REDIS_PORT = int(cfg.get('redis', 'port'))

except:
    logger.critical("Please set your config variables properly in %s before running destroy-job.py." %args.config)
    sys.exit(2)

beanstalk = beanstalkc.Connection(host=BEANSTALK_HOST, port=BEANSTALK_PORT)
beanstalk.connect()
beanstalk.watch(BEANSTALK_TUBE)

#connect to redis
rserver = redis.Redis(REDIS_HOST, REDIS_PORT)

logger.info("Starting up deletion queue worker")

while True:
    job = beanstalk.reserve()
    jobstr = job.body
    #TODO: delete job only after tweet is deleted, and come up with convoluted strategy to keep jobs that fail
    job.delete()
    tweet = json.loads(jobstr)



    try:
        #job will consist of tweet[id] and tweet[screenname] -- need to retrieve token and secret from redis
        cred = rserver.get("credentials:"+tweet['screen_name'])
        cred = json.loads(cred)
        t = Twython(CONSUMER_KEY, CONSUMER_SECRET, cred['token'], cred['secret'])
        t.destroy_status(id=tweet['id'])

        #INCREMENT COUNT IN REDIS
        logger.info("deleted tweet "+ str(tweet['id']))
        rserver.incr("deletecount:"+tweet['screen_name'], 1)
        rserver.incr("globaldeletecount", 1)
    except TwythonAuthError:
        # user has revoked access; mark them as disabled and move on
        logger.warning("%s has revoked access; removing credentials"%screen_name)
        rserver.delete("since_id"+screen_name)
        rserver.delete("deletecount"+screen_name)
        rserver.delete("credentials:"+screen_name)
        rserver.lrem("users", screen_name, 0)
