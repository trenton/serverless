#!/usr/bin/env python3

from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1
from requests_oauthlib import OAuth1Session
import base64
import boto3
import configparser
import hashlib
import hmac
import json
import os
import requests
import twitter
import urllib.parse
import yaml

aws = boto3.Session()
rek = aws.client('rekognition')

# skip if this is the source of the event
skip_sources = ['TrentonTheBotDadJokes']

oauth_base_url = 'https://api.twitter.com'
base_url = 'https://api.twitter.com/1.1'

app_env_name = "dev"

consumer_secret = None
api_key = None
api_secret_key = None
access_token = None
access_token_secret = None
dry_run = True if 'DRY_RUN' in os.environ else False


def do_tweet(status, in_reply_to=None):
    print(f"replying to {in_reply_to}")
    if not dry_run:
        out = twitter.PostUpdate(
            status,
            in_reply_to_status_id=in_reply_to,
            auto_populate_reply_metadata=True,
        )
    else:
        out = {"did not post": status}

    return out

def do_crc(crc_token):
    if crc_token:
        print(f"digesting {crc_token}")

        digest = hmac.new(
            twitter_config['api_secret_key'].encode(),
            msg=crc_token.encode(),
            digestmod=hashlib.sha256
        ).digest()

        digest_str = base64.b64encode(digest).decode()

        return {
            "body": {
                'response_token': 'sha256=' + digest_str,
            },

        }
    else:
        return {
            "statusCode": 418,
            "body": {},
        }

def fixup_for_api_gw(target):
    def wrapper(*args, **kwargs):
        response = target(*args, **kwargs)

        if 'statusCode' not in response:
            response['statusCode'] = 200

        if "content-type" not in [x.lower() for x in response.get('headers', [])]:
            response['headers'] = {
                "Content-Type": "application/json; charset=utf-8",
            }

        response['body'] = json.dumps(response['body'])

        return response

    return wrapper

def find_media(activity):
    #if activity.get('in_reply_to_user_id'):
    #    print('Looks like a reply, skipping')
    #    return None

    # avoid echo chamber
    for skip in skip_sources:
        if skip.lower() in activity['source'].lower():
            print(f"source is on my skip list: {activity['source']}")
            return None

    for media in activity['entities']['media'][0:1]:
        if media['type'] == 'photo':
            return media['media_url']

def identify_object(url):
    r = requests.get(url)
    if r.status_code == 200:
        r = rek.detect_labels(
            Image={'Bytes': r.content},
            MaxLabels=5,
            MinConfidence=0.8,
        )

        return [label['Name'].lower() for label in r['Labels']]
    else:
        print(f"Failed to get {url}: {r.status_code} {r.text}")


def handle_twitter_event(activities):
    for activity in activities.get('tweet_create_events'):
        picture_url = find_media(activity)
        if picture_url:
            print(f"found {picture_url}")
            try:
                labels = identify_object(picture_url)
            except Exception as e:
                print("failed to identify: " + e)

            if labels:
                message = format_message(labels)
                print(f"Posting {message}")
                do_tweet(message, in_reply_to=activity['id_str'])
        else:
            print(f"no pictures in {activity['id']}")


@fixup_for_api_gw
def handler(event, context):
    #>>> ipaddress.ip_address('199.59.150.172') in ipaddress.ip_network('199.59.148.0/22')

    print(json.dumps(event))
    try:
        print(event['body'])
    except Exception:
        pass

    # could replace with a event.get(...)
    if 'queryStringParameters' in event and event['queryStringParameters']:
        crc_token = event.get('queryStringParameters', {}).get('crc_token', None)
    else:
        crc_token = None

    if crc_token:
        r = do_crc(crc_token)
        return r
    else:
        handle_twitter_event(json.loads(event['body']))
        return {
            "body": {'no': 'way'},
        }

def do_register_webhook():
    session = requests.Session()

    # get a bearer token. there's probably a way to do this with the OAuth2 object
    # consider also twitter.Api.GetAppOnlyAuthToken
    token_url = f"{oauth_base_url}/oauth2/token"
    data={
        'grant_type': 'client_credentials',
    }
    r = session.post(token_url, data=data, auth=HTTPBasicAuth(twitter_config['api_key'], twitter_config['api_secret_key']))
    #print(r, r.text)

    token = json.loads(r.text)['access_token']
    #print(token)

    # list all webhooks
    r = session.get(f'{base_url}/account_activity/all/{app_env_name}/webhooks.json', headers={'Authorization': f'Bearer {token}'})
    #print(r, r.text)

    if r.status_code != 200:
        print(f"Failed to get webhooks: {r.status_code} {r.text}")
    else:
        webhook = json.loads(r.text)
        webhook_id = webhook[0]['id']
        print(f"webhook id: {webhook_id}")

    twitter_uc = OAuth1Session(
        twitter_config['api_key'],
        twitter_config['api_secret_key'],
        twitter_config['access_token'],
        twitter_config['access_token_secret'],
    )

    # verify crc of existing webhook
    webhook_url = f"{base_url}/account_activity/all/{app_env_name}/webhooks/{webhook_id}.json"
    r = twitter_uc.put(webhook_url)
    if r.status_code == 204:
        print("webhook CRC was valid")
    else:
        print(r, r.text)

    # register a new webhook
    hookback_url = "https://lh9zhnficg.execute-api.us-west-2.amazonaws.com/prod/hookback"
    webhook_url = f"{base_url}/account_activity/all/{app_env_name}/webhooks.json?url={urllib.parse.quote_plus(hookback_url)}"
    #print(f'Registration at {webhook_url}')
    #r = twitter_uc.post(webhook_url, data={})
    #print(r, r.text)

def format_message(options):
    if len(options) == 0:
        return "Hmmm… I'm not sure"

    message = f"Kinda looks like a {options[0]}"
    # https://stackoverflow.com/questions/20336524/verify-correct-use-of-a-and-an-in-english-texts-python
    if len(options) > 1:
        message += ". Could also be a "
        message += " or a ".join(options[1:])

    return message + '.'

def do_subscribe():
    trenton_config = dict(config['trenton'].items())

    trenton_auth = OAuth1(
         twitter_config['api_key'],
         twitter_config['api_secret_key'],

         trenton_config['oauth_token'],
         trenton_config['oauth_token_secret'],
    )

    subscriptions_url = f"{base_url}/account_activity/all/{env_name}/subscriptions.json"
    r = session.post(subscriptions_url, auth=trenton_auth)

    print(r)
    print(r.text)

config = configparser.ConfigParser()
config.read('config.ini')
twitter_config = dict(config['twitter'].items())

twitter = twitter.Api(
    consumer_key=twitter_config['api_key'],
    consumer_secret=twitter_config['api_secret_key'],
    access_token_key=twitter_config['access_token'],
    access_token_secret=twitter_config['access_token_secret'],
)

if __name__ == "__main__":
    #do_register_webhook()
    #print(twitter.GetUserTimeline(screen_name='trentonl'))
    #print(do_tweet('check it'))
    #print(handler({}, {}))
    for tweetf in ['test/tweet001.raw', 'test/tweet002.raw']:
        with open(tweetf, 'r') as tf:
            tweet = tf.read() 
        print(tweet)
        print(json.loads(json.loads(tweet)))

        handle_twitter_event(json.loads(json.loads(tweet)))

    #print(json.dumps(identify_object('https://en.wikipedia.org/wiki/Jaguar#/media/File:Jaguar_(Panthera_onca_palustris)_male_Three_Brothers_River_(cropped).JPG')))
    #print(format_message([]))
    #print(format_message(['one']))
    #print(format_message(['one', 'two']))
    #print(format_message(['one', 'two', '3', '4']))

