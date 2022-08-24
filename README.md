# Prerequisites
- ```>=python 3.8.9```
- ```pip3```
- [AWS Configuration](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#configuration)

# Installation
```python3 -m pip install -r requirements.txt```

# Usage
```
usage: ec2_stack_creation.py [-h] [--key-pair-name KEY_PAIR_NAME] [--stack-name STACK_NAME]

optional arguments:
  -h, --help            show this help message and exit
  --key-pair-name KEY_PAIR_NAME
                        New or existing key pair name to be used for EC2 Cloud Formation. (default: spots-keypair)
  --stack-name STACK_NAME
                        Name of stack to created (default: spots-ec2-stack)
```
