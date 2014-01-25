Python Amazon ec2 deployment script
========================

Python script for amazon ec2 deployment.

This script:<br />
    1) Creates an image form an existing instance<br />
    2) Launches X amount of instances from image<br />
    3) Adds instances to the specified load balancer<br />
    4) Removes old instances from load balancer<br />
    5) Creates an image from one of the old instances.<br />
    6) Terminates old instances<br />



Usage:
------

python deploy.py -d [String. Config file directory path] -p [String. Production load balancer name] -t [Integer. Total number of instanced to produce. Optional - default 2] -m [Integer. Timeout in minutes for each step. Optional - default 5]

    python deploy.py -d /var/log/deploy -p XXX-lb


Configuration file - deploy.conf, is to be located as specified in -d parameter.<br />

    ACCESS_KEY_ID = 'Your Amazon access key'
    SECRET_ACCESS_KEY = 'Your Amazon secret key'
    REGION = 'The region name. Eg. eu-west-1'
    STAGER_ID = 'Instance id of your staging server. e.g. i-12345678'
    INSTANCE_TYPE = 'Instance type. Eg, m1.small'
    SECURITY_GROUP = 'Security group name. e.g. my-security-group'
    KEY_PAIR = 'Key pair name'
    BASE_PATH = 'Desired location for log. e.g. /var/log/deploy/'

Logger is set to legible secure state. To get full report set logging to DEBUG.<br />
Log file must have write permissions
