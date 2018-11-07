#!/usr/bin/env python3

import configparser
from twitter import *
import os
import yaml
import requests

# [twitter]
# api_key=SMOF9tAoc3fDXwkooQJ7IKREJ
# api_secret_key=iXTNDCD8qu20qP1QKwzslGQyfvrAzVLwxCWZx2lSDrk1j0vBss
# access_token=17141223-D391XQglTu5VirM8KAaeK7M7RQF3Qeh6SGaK4k7k1
# access_token_secret=7BNsCoonsoUkccI58ctNj6tMorphf7ldwUg0KSHxyJdxF


api_key=None
api_secret_key=None
access_token=None
access_token_secret=None
do_update=True
at_whom="trentonl"
twitter=None


# def init(api_key=None, api_secret_key=None, access_token=None, access_token_secret=None, do_update=False):
#     print("doing init()")
#     twitter = Twitter(
#         auth=OAuth(access_token, access_token_secret, api_key, api_secret_key),
#     )
# 

def get_joke():
    endpoint = 'https://icanhazdadjoke.com/'
    response = requests.get(
        endpoint,
        headers = {
            'Accept': 'application/json',
        },
    )

    # use json... had charset problems with plain/text
    if response.status_code == requests.codes.ok:
        joke = yaml.load(response.text)
        return joke['joke']
    else:
        raise RuntimeError(f"Got {requests.status_code} from {endpoint}")


def handle(event, context, api_key=None, api_secret_key=None, access_token=None, access_token_secret=None, do_update=False):
    bird = Twitter(
        auth=OAuth(access_token, access_token_secret, api_key, api_secret_key),
    )

def handler(event, context):
    return do_tweet()

def do_tweet():
    #bird = Twitter(
    #    auth=OAuth(access_token, access_token_secret, api_key, api_secret_key),
    #)

    #print(yaml.dump(bird.statuses.user_timeline(screen_name="trentonl")[0]))

    joke=get_joke()
    status=f"@{at_whom}, it's time for another one…\n\n{joke}\n\n#noServerNovember"

    if do_update:
        out = twitter.statuses.update(status=status)
    else:
        out = {"did not post": status}

    print(yaml.dump(out))
    return out

# in mainline, read from config
config = configparser.ConfigParser()
config.read('config.ini')

twitter_config = dict(config['twitter'].items())
#print(twitter_config)
#init(**twitter_config)
#handle(None, None, do_update=True, **twitter_config)

do_update = True

twitter = Twitter(
    auth=OAuth(
        twitter_config['access_token'],
        twitter_config['access_token_secret'],
        twitter_config['api_key'],
        twitter_config['api_secret_key'],
    ),
)

if __name__ == "__main__":
    do_update = False
    do_tweet()

# as module, read from environment
# else:
#     api_key=os.environ.get('API_KEY')
#     api_secret_key=os.environ.get('API_SECRET_KEY')
#     access_token=os.environ.get('ACCESS_TOKEN')
#     access_token_secret=os.environ.get('ACCESS_TOKEN_SECRET')
#     at_whom=os.environ.get('AT_WHOM')
# 
#     twitter = Twitter(
#         auth=OAuth(access_token, access_token_secret, api_key, api_secret_key),
#     )
# 
