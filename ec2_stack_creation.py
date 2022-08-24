import botocore
import boto3
import requests
import argparse
import logging
from pathlib import Path

logger = logging.getLogger('ec2_stack_creation')
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

EC2_TEMPLATE_FILE = Path(__file__).resolve().parent.joinpath('cloud_formation_templates', 'ec2_template.json')
SSH_PATH = Path.home().joinpath('.ssh')

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--key-pair-name', help='New or existing key pair name to be used for EC2 Cloud Formation.', default='spots-keypair')
    parser.add_argument('--stack-name', help='Name of stack to created', default='spots-ec2-stack')
    args = parser.parse_args()
    logger.debug(args)
    public_ip = get_public_ip()


    if key_pair_exists(args.key_pair_name):
        logger.info(f'Found existing {args.key_pair_name}. Using for stack creation')
        create_ec2_cloud_formation(args.key_pair_name, public_ip, args.stack_name)
        ec2_info = get_stack_ec2_info(args.stack_name)
        wait_for_ec2_ready(ec2_info["id"])
        logger.info(f'Connect to ec2 with command: ssh -i <your-private-key> ec2-user@{ec2_info["ip"]}')

    if not key_pair_exists(args.key_pair_name):
        logger.info(f'Key Pair {args.key_pair_name} was not found. Creating KeyPair')
        valid_key_pair_name = validate_ec2_key_pair(args.key_pair_name)
        if valid_key_pair_name == args.key_pair_name:
            logger.debug(f'{args.key_pair_name} is Valid. Creating {args.key_pair_name} KeyPair')
            response = create_ec2_key_pair(valid_key_pair_name)
            logger.info(f'{args.key_pair_name} created.')
            write_key_file(valid_key_pair_name, response['KeyMaterial'])
            logger.info(f'Key file written {SSH_PATH.joinpath(valid_key_pair_name)}_rsa')
            create_ec2_cloud_formation(valid_key_pair_name, public_ip, args.stack_name)
            ec2_info= get_stack_ec2_info(args.stack_name)
            wait_for_ec2_ready(ec2_info["id"])
            logger.info(f'Connect to ec2 instance with command: ssh -i {SSH_PATH.joinpath(valid_key_pair_name)}_rsa ec2-user@{ec2_info["ip"]}')

def key_pair_exists(key_pair_name):
    key_found = False
    client = boto3.client('ec2')
    response = client.describe_key_pairs()
    for keypair in response.get('KeyPairs'):
        if keypair.get('KeyName') == key_pair_name:
            key_found = True
            return key_found
    return key_found

def write_key_file(key_pair_name, private_key):
    keyfile = SSH_PATH.joinpath(f'{key_pair_name}_rsa')
    keyfile.parent.mkdir(parents=True, exist_ok=True)

    with keyfile.open("w", encoding ="utf-8") as f:
        f.write(private_key)

    keyfile.chmod(0o600)

def get_public_ip():
    response = requests.get('https://api64.ipify.org?format=json')
    return response.json()['ip']

def create_ec2_key_pair(key_pair_name):
    try:
        client = boto3.client('ec2')
        response = client.create_key_pair(
            KeyName=key_pair_name,
            TagSpecifications=[{
                'ResourceType': 'key-pair',
                'Tags': [{
                  'Key': 'CreatedBy',
                  'Value': 'boto3'
                }]
            }])
        return response
    except botocore.exceptions.ClientError as e:
        logger.error(e)
        exit(1)

def validate_ec2_key_pair(key_pair_name):
    try:
        client = boto3.client('ec2')
        response = client.create_key_pair(
            KeyName=key_pair_name,
            DryRun=True,
            TagSpecifications=[{
                'ResourceType': 'key-pair',
                'Tags': [{
                  'Key': 'CreatedBy',
                  'Value': 'boto3'
                }]
            }])
    except botocore.exceptions.ClientError as e:
        if e.response['Error'].get('Code') == 'DryRunOperation':
            return(key_pair_name)
        else:
            logger.error(response)
            exit(1)


def create_ec2_cloud_formation(key_pair_name, public_ip, stack_name):
    template = ''
    with open(EC2_TEMPLATE_FILE, 'r') as f:
        template = f.read()

    client = boto3.client('cloudformation')
    response = client.create_stack(
        StackName = stack_name,
        TemplateBody = template,
        Parameters = [
            {'ParameterKey': 'KeyName', 'ParameterValue': key_pair_name},
            {'ParameterKey': 'SSHLocation', 'ParameterValue': f'{public_ip}/32'}
        ]
    )
    logger.debug(response)
    waiter = client.get_waiter('stack_create_complete')
    logger.info('Waiting for stack to be ready')
    waiter.wait(StackName=stack_name)
    logger.info('Stack creation complete')

def get_stack_ec2_info(stack_name):
    client = boto3.client('cloudformation')
    response = client.describe_stacks(StackName=stack_name)
    instance_info = {'id': '', 'ip': ''}
    for output in response['Stacks'][0]['Outputs']:
        if output.get('OutputKey') == 'InstanceId':
            instance_info['id'] = output.get('OutputValue')
        if output.get('OutputKey') == 'PublicIP':
            instance_info['ip'] = output.get('OutputValue')

    return instance_info

def wait_for_ec2_ready(ec2_instance_id):
    client = boto3.client('ec2')
    waiter = client.get_waiter('instance_running')
    logger.info('Waiting for ec2 ssh to be ready')
    waiter.wait(Filters=[{'Name':'instance-id', 'Values':[ec2_instance_id]}])

if __name__ == "__main__":
    main()
