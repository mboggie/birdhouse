# Archive the tweets you want

A service that will monitor specified accounts (at first, your list of friends you follow) and archive their tweets in a database.

## Status

Once properly installed and configured, birdhouse will collect the tweets from your timeline. (Testing is underway to ensure that the ull timeline is captured while not hitting rate limits.) Most cases of error and exception have been handled and tested. Optimizations, including temporary suspension, will follow at a later time. Pull requests are welcome.

## Requirements

- Uses the Twython library for Twitter authentication
- Uses Redis to store user credentials and tweets
- Expects you to have saved a local config file (.cfg) with consumer tokens, beanstalk and redis ports, etc. (use sample.cfg as a guide)
- Consists of 3 processes:
	- `main.py`: Hosts the web front-end for Twitter OAuth, and for configuring capture settings. Scheduled via system services; see conf file in `init_scripts`.
	- `birdhouse-mon.py`: For each OAuthed user, periodically wakes up and downloads their preferred stream. Scheduled using cron or other means: see example cron addition in `init_scripts`.

## Development tips

This project likes it if you use `virtualenv` to manage your Python requirements and environments (and generally, it's a not-bad idea to do that anyway.) To get started, do the following at the root of the project (once you've cloned/downloaded it):
	* `virtualenv --no-site-packages VIRTUAL`
	* `source VIRTUAL/bin/activate`
	* `pip install -r requirements.txt`

(For more on using virtualenv, go here: https://blog.dbrgn.ch/2012/9/18/virtualenv-quickstart/)

Now, just create a config file (`cat sample.cfg > birdhouse.cfg`), edit your preferences, and run it: `python main.py birdhouse.cfg`

## To Do

- If a link is present in the tweet, retrieve the link's content and save it for later as well
- Implement Twitter List selection (i.e. don't hoover my whole timeline, just these few people I follow)
- Implement screenname by screenname collection (i.e. I don't want to follow this person, or for them to know I've added them to a list, but I want to collect their Tweets anyway)
