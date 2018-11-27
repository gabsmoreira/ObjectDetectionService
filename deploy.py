import json
from pprint import pprint
import boto3
import os

with open('credentials.json') as f:
    data = json.load(f)

KEY_PAIR_NAME = data["KeyPair"]
SECURITY_GROUP = data["SecurityGroupName"]
IMAGE_ID = data["ImageId"]
DESCRIPTION = 'None'
OWNER_NAME = 'admin'

AWSCRED = [data["AWSAccessKeyId"], data["AWSSecretAccessKey"]]

INIT_SCRIPT = f"""#!/bin/bash
            echo "updating apt-get ..."
            sudo apt-get -y update 
            sudo apt-get install -y python3-pip

            echo "Installing python dependencies ..."
            sudo pip3 install flask
            sudo pip3 install boto3
            echo "Cloning git repo ..."
            pwd
            cd
            pwd
            git clone https://github.com/gabsmoreira/ObjectDetectionService.git
            cd ObjectDetectionService
            echo "Starting server ..."
            python3 load_balancer.py {AWSCRED[0]} {AWSCRED[1]}
            """

ec2 = boto3.client("ec2", region_name="us-east-1")


# Key pair 
key_pair_exists = False
kps = ec2.describe_key_pairs()
for kp in list(kps.values())[0]:
    if (kp["KeyName"] == KEY_PAIR_NAME):
        print('Using existing key pair')
        key_pair_exists = True
if(key_pair_exists == False):
    print('Creating key pair')
    created = ec2.create_key_pair(KeyName=key_pair_name)
    key_file = open(key_pair_name + ".pem", "w")
    key_file.write(created["KeyMaterial"])
    os.chmod("./" + key_pair_name + ".pem", 0o400)


# security group
security_group_exists = False
sgs = ec2.describe_security_groups()
for sg in list(sgs.values())[0]:
    if (sg["GroupName"] == SECURITY_GROUP):
        security_group_id = sg["GroupId"]
        security_group_exists = True
        print(f'Using existing security group: {SECURITY_GROUP} - {security_group_id}')
        break

if(security_group_exists == False):
    print('Creating security group')
    vpcs = ec2.describe_vpcs()
    vpc = vpcs.get('Vpcs', [{}])[0].get('VpcId', '')
    response = ec2.create_security_group(GroupName=SECURITY_GROUP,
                                        Description=DESCRIPTION,
                                        VpcId=vpc)
    security_group_id = response['GroupId']
    auth = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
            'FromPort': 5000,
            'ToPort': 5000,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])


if(IMAGE_ID == None):
    IMAGE_ID = 'ami-0ac019f4fcb7cb7e6'


print(IMAGE_ID, KEY_PAIR_NAME,security_group_id)
try:
    load_balancer = ec2.run_instances(
        ImageId=IMAGE_ID, 
        MinCount=1, MaxCount=1,
        InstanceType="t2.medium",
        KeyName=KEY_PAIR_NAME,
        SecurityGroupIds=[security_group_id],
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Owner","Value": OWNER_NAME}, {"Key": "Type","Value": "loadbalancer"}]
            }],
        UserData=INIT_SCRIPT
        )
    # print("Instance creation response: \n", load_balancer)
    # pass

    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[load_balancer['Instances'][0]['InstanceId']])
    instance_id = load_balancer['Instances'][0]['InstanceId']
    data = ec2.describe_instances()
    instances = [d['Instances'][0] for d in data['Reservations']]
    for instance in instances:
        if(instance['Tags'] == None):
            continue
        for idx, tag in enumerate(instance['Tags'], start=1):
            if(tag['Value'] == OWNER_NAME and instance['InstanceId'] == instance_id):
                ip = instance['NetworkInterfaces'][0]['Association']['PublicIp']
                web = instance['NetworkInterfaces'][0]['Association']['PublicDnsName']


    print(f'IP: {ip}')
    print(f'ACCESS: {web}')
except ClientError as e:
    print("An error occured while trying to create an Instance")
    print(e)
