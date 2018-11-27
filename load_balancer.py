import threading
import requests
import boto3
import time
import signal
from flask import Flask, request, jsonify, Response
import json
import sys

# CONSTANTS
TIMEOUT = 5
RUN_ALL = True
RUNNING_INSTANCES = []
NUMBER_OF_INSTANCES = 3
INSTANCES_RUNNING_ACTUAL = 3
LOAD_BALANCER_REQ = 0
INSTANCE_TYPE = 't2.medium'
OWNER_NAME = 'admin'
SCRIPT = """#!/bin/bash
        echo "updating apt-get ..."
        sudo apt-get -y update
        sudo apt-get install -y python3-pip

        echo "Installing python dependencies ..."
        sudo pip3 install flask
        sudo pip3 install numpy
        sudo pip3 install gluoncv
        sudo pip3 install mxnet
        echo "Cloning git repo ..."
        pwd
        cd
        pwd
        git clone https://github.com/gabsmoreira/ObjectDetectionService.git
        cd ObjectDetectionService
        echo "Starting server ..."
        python3 watson_server2.py
        """
TAGS =[{
        "ResourceType": "instance",
        "Tags": [{"Key": "Owner","Value": OWNER_NAME}]
        }]
# ACCESS_ID = sys.argv[1]
# ACCESS_KEY = sys.argv[2]
EC2 = boto3.resource('ec2', region_name='us-east-1')
client = boto3.client('ec2', region_name='us-east-1')


def get_instances_data():
    ''' Function to get instance params '''
    data = client.describe_instances()
    instances = [d['Instances'][0] for d in data['Reservations']]
    for instance in instances:
        is_load_balancer = False
        if(instance['Tags'] == None):
            continue
        for idx, tag in enumerate(instance['Tags'], start=1):
            # print(tag['Value'])
            if(tag['Key'] == 'Type' and tag['Value'] == 'loadbalancer'):
                for idx, tag in enumerate(instance['Tags'], start=1):
                    if(tag['Value'] == OWNER_NAME and instance['State']['Name'] == 'running'):
                        # print(tag)
                        sec_group_id = [sec['GroupId'] for sec in instance['NetworkInterfaces'][0]['Groups']]
                        key_pair_name = instance['KeyName']
                        image_id = instance['ImageId']
                        return sec_group_id, key_pair_name, image_id
    return None
            

# Params retrieved from load balancer instance
SECURITY_GROUP_IDs, KEY_PAIR_NAME, IMAGE_ID = get_instances_data()
print(SECURITY_GROUP_IDs, KEY_PAIR_NAME, IMAGE_ID)

def create_instance(key_pair, security_group, instance_type):
    print('Creating instance')
    '''Create instance based on key pair, security group and instance type '''
    try:
        instance = client.run_instances(
            ImageId=IMAGE_ID, 
            MinCount=1, MaxCount=1,
            InstanceType=INSTANCE_TYPE,
            KeyName=KEY_PAIR_NAME,
            SecurityGroupIds=SECURITY_GROUP_IDs,
            TagSpecifications=TAGS,
            UserData=SCRIPT
            )
    except Exception as e:
        print('Error to create instance')
        print(e)
    waiter = client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance['Instances'][0]['InstanceId']])
    instance_id = instance['Instances'][0]['InstanceId']
    data = client.describe_instances()
    instances = [d['Instances'][0] for d in data['Reservations']]
    for instance in instances:
        if(instance['Tags'] == None):
            continue
        for idx, tag in enumerate(instance['Tags'], start=1):
            if(tag['Value'] == OWNER_NAME and instance['InstanceId'] == instance_id):
                ip = instance['NetworkInterfaces'][0]['Association']['PublicIp']

    done = False
    print(ip)
    formated_ip = ip.replace('.', '-')
    print('http://ec2-' + formated_ip + '.compute-1.amazonaws.com:5000/healthcheck')
    while done == False:
        try:
            r = requests.get('http://ec2-' + formated_ip + '.compute-1.amazonaws.com:5000/healthcheck', timeout=TIMEOUT)
            if(r.status_code == 200):
                done = True
        except Exception as e:
            pass
        time.sleep(2)

    update_available_instances()
    print('CREATED instance ', instance_id)
    



def get_instances_ip():
    ''' Get all instances with the owner '''
    global OWNER_NAME
    global EC2
    running_instances = []
    for instance in EC2.instances.all():
        if(instance.tags == None):
          continue
        for idx, tag in enumerate(instance.tags, start=1):
            if(tag['Value'] == OWNER_NAME and instance.state['Code'] != 48):
                running_instances.append({instance.id : instance.public_dns_name})
    return running_instances


def update_available_instances():
    ''' Update available instances list '''
    global RUNNING_INSTANCES
    # print('Updating available instances')
    RUNNING_INSTANCES = get_instances_ip()
    

def destroy_instance(instance_id):
    print(f'Destroying instance {instance_id}')
    for instance in EC2.instances.all():
        if(instance.tags == None):
          continue
        for idx, tag in enumerate(instance['Tags'], start=1):
          if(tag['Key'] == 'Type' and tag['Value'] != 'loadbalancer'):
            for idx, tag in enumerate(instance.tags, start=1):
                if(tag['Value'] == OWNER_NAME and instance.state['Code'] != 48 and instance.id == instance_id):
                waiter = client.get_waiter('instance_terminated')
                try:
                    update_available_instances()
                    client.terminate_instances(InstanceIds=[instance.id])
                    waiter.wait(InstanceIds=[instance.id])
                    # INSTANCES_RUNNING -=1
                    print('Destroyed instance ', instance.id)

                except:
                    print('Error to delete instance')
                # ec2.instances.filter(InstasnceIds=[instance.id]).terminate()

def signal_handler(sig, frame):
    RUN_ALL = False
    exit(0)
signal.signal(signal.SIGINT, signal_handler)


def check_health():
    '''Function that will run inside the thread. Check for problematic instances'''
    while RUN_ALL:
        for instance in RUNNING_INSTANCES:
            # print(instance)
            for instance_id in instance:
                ip = instance[instance_id]
                # print('http://' + ip +':5000/healthcheck')
                try:
                    # formated_ip = ip.replace('.', '-')
                    r = requests.get('http://' + ip +':5000/healthcheck', timeout=TIMEOUT)
                    # print(f'Requested: {ip}')
                except Exception as e:
                    print(e)
                    destroy_instance(instance_id)
                    create_instance(KEY_PAIR_NAME, SECURITY_GROUP_IDs, INSTANCE_TYPE)

        update_available_instances()
        dif = NUMBER_OF_INSTANCES - len(RUNNING_INSTANCES) 
        if(dif != 0):
            if(dif < 0):
                for i in range(-dif):
                    destroy_instance(list(RUNNING_INSTANCES[0].keys())[0])
            else:
                for i in range(dif):
                    create_instance(KEY_PAIR_NAME, SECURITY_GROUP_IDs, INSTANCE_TYPE)
        else:
            print('Right number of instances')
            pass
        time.sleep(3)


RUNNING_INSTANCES = get_instances_ip()

healthchecker = threading.Thread(target=check_health)
healthchecker.daemon = True
healthchecker.start()
# healthchecker.join()

app = Flask(__name__)
@app.route('/')
def hello_world():
    return 'Hello, World from Load Balancer!'


@app.route('/predict', methods = ['GET'])
def predict_route():
    global RUNNING_INSTANCES
    global LOAD_BALANCER_REQ
    image_url = request.args.get('image_url', default = None, type = str)
    percentage_limit = request.args.get('limit', default = 0.4, type = float)
    params = {'image_url': image_url, 'percentage_limit': percentage_limit}
    ips = []
    print(LOAD_BALANCER_REQ)
    for instance in RUNNING_INSTANCES:
        for key in instance:
            ips.append(instance[key])
    try:
        print(ips[LOAD_BALANCER_REQ % len(RUNNING_INSTANCES)])
        response = requests.get('http://' + ips[LOAD_BALANCER_REQ % len(RUNNING_INSTANCES)] + ':5000/predict', params=params)
        LOAD_BALANCER_REQ +=1
        return str(response.content.decode('utf-8'))
    except Exception as e:
        print("Could not make request")
        return Response(status=404)


app.run(host='0.0.0.0', port=8000)