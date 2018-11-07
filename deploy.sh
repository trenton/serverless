#!/usr/bin/env zsh

set -euxo pipefail

AWS_REGION=us-west-2
CFN_BUCKET=cloudformation-us-west-2-645086751203
CFN_TEMPLATE_FILE=challenge20181105-dad-jokes.yaml
STACK_NAME=serverless-dadjokes

local temp_output_template=$(mktemp)'.json'

local base=$PWD

local distfile=$base/dist/dist.zip
if [ ! -d dist ]; then
	mkdir dist
else
	rm -f $distfile
fi

local build_and_upload=y
local zip_code_s3_key=nope

if [[ $build_and_upload = 'y' ]]; then
    # zip appears to be missing tar's -C option, so you need to cd. bletch.
    cd lib/python3.6/site-packages
    zip -qr9 $distfile * -x pip/\*
    cd $base
    zip -qg $distfile *.py *.ini *.yaml

    # add time since epoch to get a different value on each deploy
    # preferring portability over uniqueness, so not using a uuid
    zip_code_s3_key="${STACK_NAME}/dist-$(date +%s).zip"
    aws --region $AWS_REGION s3 cp \
      $distfile "s3://${CFN_BUCKET}/${zip_code_s3_key}"
fi

aws --region $AWS_REGION cloudformation package \
    --template-file $CFN_TEMPLATE_FILE \
    --output-template-file $temp_output_template \
    --s3-bucket $CFN_BUCKET \
    --s3-prefix "${STACK_NAME}" \
    --use-json

aws --region $AWS_REGION cloudformation deploy \
     --stack-name "${STACK_NAME}" \
     --template-file $temp_output_template \
     --capabilities CAPABILITY_NAMED_IAM \
     --s3-bucket $CFN_BUCKET \
     --parameter-overrides \
	CfnCodeS3Bucket=$CFN_BUCKET \
	CfnCodeS3Key=${zip_code_s3_key}
