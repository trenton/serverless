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

**Determine endpoint**

```
aws cloudformation describe-stacks --stack-name serverless003 |jq '.Stacks[] | .Outputs[] | select(.OutputKey == "ProdEndpoint").OutputValue'
```

## Dad Jokes

```
python3 -m venv .
pip install -r requirements.txt
DRY_RUN=yes ./dad.py
./deploy.sh
```
