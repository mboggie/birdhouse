# -*- coding: utf-8 -*-

import tornado.web
import tornado.ioloop
import tornado.gen
from twython import Twython
import tornadoredis
import redis
import os, sys, json
import argparse
import ConfigParser
import logging

class Status(tornado.web.RequestHandler):
    def get(self):
        user_key = self.get_secure_cookie('birdhouse')

        if not user_key:
            self.redirect("/")
            return
        try:
            cookie = json.loads(user_key)
            screen_name = cookie["screen_name"]
            id_str = cookie["id_str"]
        except:
            #doublecheck the cookie isn't hosed
            #if it is, kill it and have the user come back thru the oauth process
            self.clear_cookie('birdhouse')
            self.redirect("/")
            return
        creds = rserver.get("credentials:"+id_str)
        if creds is None:
            #user has revoked access previously; redirect them to the homepage to oauth again
            #note: in most cases screen_name will not be in list here, but just in case.
            rserver.lrem("users", id_str, 0)
            rserver.delete("since_id:"+id_str)
            self.clear_cookie('birdhouse')
            self.redirect("/")
        else:
    		#TODO: call Twitter here to get latest screen_name, name, etc.
            #(it may change after user oauths)
            self.render("status.html", screen_name=screen_name)

class LoginSuccess(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self):
        oauth_verifier = self.get_argument('oauth_verifier')
        oauth_token = self.get_argument('oauth_token')
        secret = self.get_secure_cookie("bh_auth_secret")
        logger.debug("trying to finish auth with "+ secret)
        twitter = Twython(CONSUMER_KEY, CONSUMER_SECRET, oauth_token, secret)
        final_step = twitter.get_authorized_tokens(oauth_verifier)
        logger.debug(json.dumps(final_step))
        screen_name = final_step['screen_name']
        id_str = final_step['user_id']
        credentials = {}
        credentials['token'] = final_step['oauth_token']
        credentials['secret'] = final_step['oauth_token_secret']
        # save login info
        yield tornado.gen.Task(conn.set, "credentials:"+id_str, json.dumps(credentials))
        yield tornado.gen.Task(conn.lpush, "users", id_str)
        # set cookie
        cookie_data = {"token": final_step['oauth_token'], "secret": final_step['oauth_token_secret'], "screen_name": screen_name, "id_str": id_str}
        self.set_secure_cookie("birdhouse", json.dumps(cookie_data))
        self.clear_cookie("bh_auth_token")
        self.clear_cookie("bh_auth_secret")
        self.redirect("/status")

class TwitterLoginHandler(tornado.web.RequestHandler):
    def get(self):
        if not self.get_secure_cookie('birdhouse'):
            twitter = Twython(CONSUMER_KEY, CONSUMER_SECRET)
            auth = twitter.get_authentication_tokens(callback_url= BHHOST+":"+BHPORT+'/success')
            logger.debug("Back in python from twitter.")
            oauth_token = auth['oauth_token']
            oauth_token_secret = auth['oauth_token_secret']
            self.set_secure_cookie("bh_auth_token",oauth_token)
            self.set_secure_cookie("bh_auth_secret",oauth_token_secret)
            self.redirect(auth['auth_url'])
        else:
            self.redirect('/status')

class Settings(tornado.web.RequestHandler):
    def get(self):
        self.render("settings.html")

class About(tornado.web.RequestHandler):
	def get(self):
		self.render("about.html")

class Intro(tornado.web.RequestHandler):
    def get(self):
        if not self.get_secure_cookie('birdhouse'):
            self.render("intro.html")
        else:
            self.redirect('/status')


###################################################

# setup logging
logger = logging.getLogger("birdhouse")
logger.setLevel(logging.DEBUG)
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
    BHHOST = cfg.get('birdhouse', 'host')
    BHPORT = cfg.get('birdhouse', 'port')
    REDIS_HOST = cfg.get('redis', 'host')
    REDIS_PORT = int(cfg.get('redis', 'port'))
    COOKIE_SECRET = cfg.get('birdhouse', 'cookie_secret')

except:
    logger.critical("Please set your config variables properly in %s before running main.py." % args.config)
    sys.exit(2)

conn = tornadoredis.Client(host=REDIS_HOST, port=REDIS_PORT)
conn.connect()
rserver = redis.Redis(REDIS_HOST, REDIS_PORT)

settings = dict(
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    static_path=os.path.join(os.path.dirname(__file__), "static"),
    cookie_secret=COOKIE_SECRET,
    twitter_consumer_key=CONSUMER_KEY,
    twitter_consumer_secret=CONSUMER_SECRET,
    debug=True
)

application = tornado.web.Application([
    (r"/", Intro),
    (r"/login", TwitterLoginHandler),
    (r"/success", LoginSuccess),
    (r"/status", Status),
    (r"/settings", Settings)
], **settings)

if __name__ == "__main__":
	#schedule the listener - it will be responsible for setting queues up and starting schedulers

	#start tornado listener for web interface
    application.listen(BHPORT)
    logger.info("Birdhouse Logger Inner starting on port %s" %BHPORT)
    tornado.ioloop.IOLoop.instance().start()
