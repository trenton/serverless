# Introduction

\#noServerNovember

# Challenges

1. Serverless Ipsum: https://lggqhai1jd.execute-api.us-west-2.amazonaws.com/prod/serverless
1. Dad Jokes: [Follow @TrentonL](https://twitter.com/TrentonL). You'll see them every hour.

# Runbook

## Serverless Ipsum

**Deploy**

```
aws cloudformation update-stack --stack-name serverless003 --template-body file://challenge20181105-serverless-ipsum.yaml --capabilities CAPABILITY_IAM
```

or
```
./deploy.py --cfn-bucket cloudformation-us-west-2-645086751203 --cfn-template challenge20181105-serverless-ipsum.yaml --stack-name serverless005
```

**Determine endpoint**

```
aws cloudformation describe-stacks --stack-name serverless003 |jq '.Stacks[] | .Outputs[] | select(.OutputKey == "ProdEndpoint").OutputValue'
```

## Dad Jokes

```
python3 -m venv .
pip install -r requirements.txt
DRY_RUN=yes ./dad.py
./deploy.py \
    --cfn-bucket cloudformation-us-west-2-645086751203 \
    --cfn-template challenge20181105-dad-jokes.yaml \
    --stack-name serverless-dadjokes-001 \
    --ssm-config-name dadjoke

```

## Twitter bot

Instructions incomplete. You need to sign up for [https://developer.twitter.com/en/docs/accounts-and-users/subscribe-account-activity/overview](Twitter's Account Activity API). 

```
python3 -m venv .
pip install -r requirements.txt
./twitter_picture_bot.py
./deploy.py \
	--cfn-bucket cloudformation-us-west-2-645086751203 \
	--cfn-template challenge20181112-twitter-picture-bot.yaml \
	--stack-name twitter-picture-bot \
	--ssm-config-name dadjoke 
```
