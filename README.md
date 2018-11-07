# Introduction

\#noServerNovember

# Challenges

1. Serverless Ipsum: https://lggqhai1jd.execute-api.us-west-2.amazonaws.com/prod/serverless

# Deployment notes

```
aws cloudformation update-stack --stack-name serverless003 --template-body file://challenge20181105-serverless-ipsum.yaml --capabilities CAPABILITY_IAM
```
