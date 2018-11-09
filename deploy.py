#!/usr/bin/env python3

import glob
import itertools
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

AWS_REGION = 'us-west-2'
CFN_BUCKET = 'cloudformation-us-west-2-645086751203'
CFN_TEMPLATE_FILE = 'challenge20181105-dad-jokes.yaml'
STACK_NAME = 'serverless-dadjokes-001'

_, temp_output_template = tempfile.mkstemp(suffix='.json')

project_root = os.getcwd()

distfile = f"{project_root}/dist/pydist.zip"
if not os.path.isdir('dist'):
    os.mkdir('dist')
else:
    try:
        os.remove(distfile)
    except FileNotFoundError:
        pass

build_and_upload = True
if build_and_upload:
    print(f"Making zip in {distfile}")
    with zipfile.ZipFile(distfile, 'w', zipfile.ZIP_DEFLATED) as zipf:
        python_site = 'lib/python3.6/site-packages/'
        for root, dirs, files in os.walk(python_site):
            for file in files:
                full_path = root + "/" + file
                archive_path = full_path.replace(python_site, "")

                # skip stuff not needed at runtime
                if archive_path.startswith(('pip/', 'pkg_resources/', 'pip-')):
                    continue

                if archive_path.endswith(('.pyc', '.so', '.exe')):
                    continue

                zipf.write(full_path, archive_path)

        more_files = [glob.glob(x) for x in ['*py', '*ini', '*yaml']]
        for file in itertools.chain(*more_files):
            zipf.write(file)

    # add time since epoch to get a different value on each deploy
    # preferring ergonomics over uniqueness, so not using a uuid
    zip_code_s3_key = f"{STACK_NAME}/dist-{int(time.time())}.zip"
    s3_target = f's3://{CFN_BUCKET}/{zip_code_s3_key}'

    print(f"Copying to {distfile} to {s3_target}")
    s3_cmd = f'aws --region {AWS_REGION} s3 cp {distfile} {s3_target}'
    cp_result = subprocess.run(
        re.split(r'\s+', s3_cmd),
        timeout=333,
        check=True,
    )

print(f"Packaging to {temp_output_template}")
package_cmd = (
    f"aws --region {AWS_REGION} cloudformation package"
    f"    --template-file {CFN_TEMPLATE_FILE}"
    f"    --output-template-file {temp_output_template}"
    f"    --s3-bucket {CFN_BUCKET}"
    f"    --s3-prefix {STACK_NAME}"
    f"    --use-json"
)
subprocess.run(re.split(r'\s+', package_cmd), timeout=333, check=True)

print(f"Deploying stack {STACK_NAME}")
deploy_cmd = (
    f"aws --region {AWS_REGION} cloudformation deploy"
    f"     --stack-name {STACK_NAME}"
    f"     --template-file {temp_output_template}"
    f"     --capabilities CAPABILITY_NAMED_IAM"
    f"     --s3-bucket {CFN_BUCKET}"
    f"     --debug"
    f"     --parameter-overrides"
    f"	     CfnCodeS3Bucket={CFN_BUCKET}"
    f"	     CfnCodeS3Key={zip_code_s3_key}"
)
subprocess.run(re.split(r'\s+', deploy_cmd), timeout=333, check=True)
