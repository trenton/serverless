#!/usr/bin/env python3

import configparser
from twitter import *
import os
import yaml
import requests


api_key=None
api_secret_key=None
access_token=None
access_token_secret=None
dry_run=True if 'DRY_RUN' in os.environ else False

twitter=None


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


def handler(event, context):
    return do_tweet()

def do_tweet():
    joke=get_joke()

    status=f"It's time for another one…\n\n{joke}\n\n#noServerNovember"

    if not dry_run:
        out = twitter.statuses.update(status=status)
    else:
        out = {"did not post": status}

    return out

config = configparser.ConfigParser()
config.read('config.ini')

twitter_config = dict(config['twitter'].items())

twitter = Twitter(
    auth=OAuth(
        twitter_config['access_token'],
        twitter_config['access_token_secret'],
        twitter_config['api_key'],
        twitter_config['api_secret_key'],
    ),
)

if __name__ == "__main__":
    print(yaml.dump(do_tweet()))

