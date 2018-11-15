#!/usr/bin/env python3

import argparse
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
from botocore.exceptions import ClientError


class Deployer:
    DEFAULT_WAIT_FOR_READY_SECONDS = 60 * 3

    DEFAULT_AWS_REGION = 'us-west-2'

    def __init__(
            self,
            cfn_bucket, cfn_template_file, stack_name,
            ssm_config_name=None,
            region=DEFAULT_AWS_REGION,
            wait_for_ready_seconds=DEFAULT_WAIT_FOR_READY_SECONDS):
        self.cfn_bucket = cfn_bucket
        self.cfn_template_file = cfn_template_file
        self.stack_name = stack_name
        self.ssm_config_name = ssm_config_name
        self.wait_for_ready_seconds = wait_for_ready_seconds

        self.build_dir = 'build'
        self.dist_dir = 'dist'
        self.config_file = 'dist/config.ini'

        aws = boto3.Session(region_name=region)

        self.s3 = aws.resource('s3')
        self.cfn = aws.client('cloudformation')
        self.ssm = aws.client('ssm')
        self.now = int(time.time())

        # set during execution of steps
        self.dist_file = None
        self.s3_code_url = None
        self.change_set_id = None

    def setup(self):
        if not os.path.isdir(self.build_dir):
            os.mkdir(self.build_dir)

        dist_file = f"{os.getcwd()}/{self.dist_dir}/pydist.zip"
        if not os.path.isdir(self.dist_dir):
            os.mkdir(self.dist_dir)

        self.dist_file = dist_file

    def install_deps(self):
        print("Installing dependencies")
        out = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-t", self.build_dir, "-r", "requirements.txt"],
            check=True,
        )

    def download_config(self):
        if not self.ssm_config_name:
            print(f'No SSM config specified, continuing without {self.config_file}')
            return

        print(f'Downloading config to {self.config_file}')
        ssm_response = self.ssm.get_parameters(
                Names=[self.ssm_config_name],
                WithDecryption=True
        )
        config = base64.b64decode(ssm_response['Parameters'][0]['Value'])
        with open(self.config_file, 'wb') as ini:
            ini.write(config)

    def build(self):
        print(f"Making zip in {self.dist_file}")
        with zipfile.ZipFile(self.dist_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.build_dir):
                for file in files:
                    full_path = root + "/" + file
                    archive_path = full_path.replace(self.build_dir, "")

                    # skip stuff not needed at runtime
                    if archive_path.startswith(('pip/', 'pkg_resources/', 'pip-', 'bin/')):
                        continue

                    if archive_path.endswith(('.pyc', '.so', '.exe')):
                        continue

                    zipf.write(full_path, archive_path)

            more_files = [glob.glob(x) for x in ['*py', '*yaml']]
            for file in itertools.chain(*more_files):
                zipf.write(file)

            # config is optional
            if os.path.isfile(self.config_file):
                zipf.write(self.config_file, 'config.ini')

    def upload(self):
        # add time since epoch to get a different value on each deploy
        # preferring ergonomics over uniqueness, so not using a uuid
        zip_code_s3_key = f'{self.stack_name}/dist-{self.now}.zip'
        s3_url = f's3://{self.cfn_bucket}/{zip_code_s3_key}'

        print(f'Uploading to {self.dist_file} to {s3_url}')
        self.s3.Object(self.cfn_bucket, zip_code_s3_key).put(Body=open(self.dist_file, 'rb'))

        self.s3_code_key = zip_code_s3_key

    def stack_exists(self):
        try:
            self.cfn.describe_stacks(StackName=self.stack_name)
            return True
        except ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                return False
            else:
                raise e

    def create_stack(self):
        print(f"Creating stack {self.stack_name}")
        create_response = self.cfn.create_stack(
            StackName=self.stack_name,
            Capabilities=['CAPABILITY_NAMED_IAM'],
            TemplateBody=open(self.cfn_template_file, 'r').read(),
            Parameters=[
                {'ParameterKey': 'CfnCodeS3Bucket', 'ParameterValue': self.cfn_bucket},
                {'ParameterKey': 'CfnCodeS3Key', 'ParameterValue': self.s3_code_key},
            ],
        )

    def update_stack(self):
        print(f"Updating stack {self.stack_name}")
        try:
            create_response = self.cfn.update_stack(
                StackName=self.stack_name,
                Capabilities=['CAPABILITY_NAMED_IAM'],
                TemplateBody=open(self.cfn_template_file, 'r').read(),
                Parameters=[
                    {'ParameterKey': 'CfnCodeS3Bucket', 'ParameterValue': self.cfn_bucket},
                    {'ParameterKey': 'CfnCodeS3Key', 'ParameterValue': self.s3_code_key},
                ],
            )
            print(f"Update complete")
        except ClientError as e:
            if "No updates are to be performed" in e.response['Error']['Message']:
                print(f"No updates required")
            else:
                raise e

    def create_change_set(self):
        create_response = self.cfn.create_change_set(
            StackName=self.stack_name,
            Capabilities=['CAPABILITY_NAMED_IAM'],
            ChangeSetName=f'z{self.now}',
            TemplateBody=open(self.cfn_template_file, 'r').read(),
            Parameters=[
                {'ParameterKey': 'CfnCodeS3Bucket', 'ParameterValue': self.cfn_bucket},
                {'ParameterKey': 'CfnCodeS3Key', 'ParameterValue': self.s3_code_key},
            ],
        )

        change_set_id = create_response['Id']

        print(f"Waiting for change set {change_set_id} to be ready")
        wait_until = time.time() + self.wait_for_ready_seconds
        while time.time() < wait_until:
            change_set = self.cfn.describe_change_set(ChangeSetName=change_set_id)
            print(f"...status was {change_set['Status']}")

            if change_set['Status'] == 'CREATE_COMPLETE':
                self.change_set_id = change_set_id
                break
            else:
                time.sleep(3)

    def execute_change_set(self):
        print(f"Executing change set {self.change_set_id}")
        self.cfn.execute_change_set(ChangeSetName=self.change_set_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfn-bucket", required=True)
    parser.add_argument("--cfn-template", required=True)
    parser.add_argument("--stack-name", required=True)
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--skip-build", action='store_true')
    parser.add_argument("--ssm-config-name")

    args = parser.parse_args()

    deployer = Deployer(
        cfn_bucket=args.cfn_bucket,
        cfn_template_file=args.cfn_template,
        stack_name=args.stack_name,
        region=args.region,
        ssm_config_name=args.ssm_config_name,
    )

    deployer.setup()
    if not args.skip_build:
        deployer.install_deps()
        deployer.download_config()
        deployer.build()

    deployer.upload()
    if deployer.stack_exists():
        deployer.update_stack()
    else:
        deployer.create_stack()
