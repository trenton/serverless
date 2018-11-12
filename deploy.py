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


class Deployer:
    WAIT_FOR_READY_SECONDS = 60 * 3

    def __init__(self):
        aws_region = 'us-west-2'
        self.cfn_bucket = 'cloudformation-us-west-2-645086751203'
        self.cfn_template_file = 'challenge20181105-dad-jokes.yaml'
        self.stack_name = 'serverless-dadjokes-001'
        self.ssm_config_name = 'dadjoke'

        self.build_dir = 'build'
        self.dist_dir = 'dist'
        self.config_file = 'dist/config.ini'

        aws = boto3.Session(region_name=aws_region)

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
        else:
            try:
                os.remove(dist_file)
            except FileNotFoundError:
                pass

        self.dist_file = dist_file

    def install_deps(self):
        print("Installing dependencies")
        out = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-t", self.build_dir, "-r", "requirements.txt"],
            check=True,
        )

    def download_config(self):
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

            zipf.write(self.config_file, 'config.ini')

    def upload(self):
        # add time since epoch to get a different value on each deploy
        # preferring ergonomics over uniqueness, so not using a uuid
        zip_code_s3_key = f'{self.stack_name}/dist-{self.now}.zip'
        s3_url = f's3://{self.cfn_bucket}/{zip_code_s3_key}'

        print(f'Uploading to {self.dist_file} to {s3_url}')
        self.s3.Object(self.cfn_bucket, zip_code_s3_key).put(Body=open(self.dist_file, 'rb'))

        self.s3_code_key = zip_code_s3_key

    def create_change_set(self, poll=True):
        print(f"Creating change set")
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
        wait_until = time.time() + Deployer.WAIT_FOR_READY_SECONDS
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
    deployer = Deployer()

    deployer.setup()
    deployer.install_deps()
    deployer.download_config()
    deployer.build()
    deployer.upload()
    deployer.create_change_set()
    deployer.execute_change_set()
