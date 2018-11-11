#!/usr/bin/env python3

import base64
import boto3
import glob
import itertools
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile


AWS_REGION = 'us-west-2'
CFN_BUCKET = 'cloudformation-us-west-2-645086751203'
CFN_TEMPLATE_FILE = 'challenge20181105-dad-jokes.yaml'
STACK_NAME = 'serverless-dadjokes-001'
CONFIG_PARAM = 'dadjoke'

BUILD_DIR = 'build'
CONFIG_FILE = 'dist/config.ini'

WAIT_FOR_READY_SECONDS = 60 * 3

aws = boto3.Session(region_name=AWS_REGION)
s3 = aws.resource('s3')
cfn = aws.client('cloudformation')
ssm = aws.client('ssm')

now = int(time.time())

def setup():
    if not os.path.isdir(BUILD_DIR):
        os.mkdir(BUILD_DIR)

    dist_file = f"{os.getcwd()}/dist/pydist.zip"
    if not os.path.isdir('dist'):
        os.mkdir('dist')
    else:
        try:
            os.remove(dist_file)
        except FileNotFoundError:
            pass

    return dist_file

def install_deps():
    print("Installing dependencies")
    out = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-t", BUILD_DIR, "-r", "requirements.txt"],
        check=True,
    )

def download_config():
    print('Downloading config to {CONFIG_FILE}')
    ssm_response = ssm.get_parameters(Names=[CONFIG_PARAM], WithDecryption=True)
    config = base64.b64decode(ssm_response['Parameters'][0]['Value'])
    with open(CONFIG_FILE, 'wb') as ini:
        ini.write(config)

def build_and_upload(distfile):
    print(f"Making zip in {distfile}")
    with zipfile.ZipFile(distfile, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(BUILD_DIR):
            for file in files:
                full_path = root + "/" + file
                archive_path = full_path.replace(BUILD_DIR, "")

                # skip stuff not needed at runtime
                if archive_path.startswith(('pip/', 'pkg_resources/', 'pip-', 'bin/')):
                    continue

                if archive_path.endswith(('.pyc', '.so', '.exe')):
                    continue

                zipf.write(full_path, archive_path)

        more_files = [glob.glob(x) for x in ['*py', '*yaml']]
        for file in itertools.chain(*more_files):
            zipf.write(file)

        zipf.write(CONFIG_FILE, 'config.ini')

    # add time since epoch to get a different value on each deploy
    # preferring ergonomics over uniqueness, so not using a uuid
    zip_code_s3_key = f'{STACK_NAME}/dist-{now}.zip'
    s3_target = f's3://{CFN_BUCKET}/{zip_code_s3_key}'

    print(f'Uploading to {distfile} to {s3_target}')
    s3.Object(CFN_BUCKET, zip_code_s3_key).put(Body=open(distfile, 'rb'))

    return zip_code_s3_key

def create_change_set(s3_code_key, poll=True):
    print(f"Creating change set")
    create_response = cfn.create_change_set(
        StackName=STACK_NAME,
        Capabilities=['CAPABILITY_NAMED_IAM'],
        ChangeSetName=f'z{now}',
        TemplateBody=open(CFN_TEMPLATE_FILE, 'r').read(),
        Parameters=[
            {'ParameterKey': 'CfnCodeS3Bucket', 'ParameterValue': CFN_BUCKET},
            {'ParameterKey': 'CfnCodeS3Key', 'ParameterValue': s3_code_key},
        ],
    )

    change_set_id = create_response['Id']

    print(f"Waiting for change set {change_set_id} to be ready")
    wait_until = time.time() + WAIT_FOR_READY_SECONDS
    while time.time() < wait_until:
        change_set = cfn.describe_change_set(ChangeSetName=change_set_id)
        print(f"...status was {change_set['Status']}")

        if change_set['Status'] == 'CREATE_COMPLETE':
            break
        else:
            time.sleep(3)

        return change_set_id

def execute_change_set(change_set_id):
    print(f"Executing change set {change_set_id}")
    cfn.execute_change_set(ChangeSetName=change_set_id)

if __name__ == "__main__":
    dist_file = setup()

    install_deps()
    download_config()
    s3_key = build_and_upload(dist_file)
    change_set_id = create_change_set(s3_key)
    execute_change_set(change_set_id)
