# Introduction

\#noServerNovember

# Challenges

1. Serverless Ipsum: https://lggqhai1jd.execute-api.us-west-2.amazonaws.com/prod/serverless

# Deployment notes

**Build**

```
rm dist/dist.zip
zip -9 -r dist/dist.zip lib/python3.6/site-packages -x .\*
zip -9 -g dist/dist.zip . -x dist/\* bin/\* lib/\* .\*
```

**Make it so**

```
aws cloudformation update-stack --stack-name serverless003 --template-body file://challenge20181105-serverless-ipsum.yaml --capabilities CAPABILITY_IAM
```

**Determine endpoint**

```
aws cloudformation describe-stacks --stack-name serverless003 |jq '.Stacks[] | .Outputs[] | select(.OutputKey == "ProdEndpoint").OutputValue'
```
