import boto, time, sys, logging, getopt
from boto import regioninfo
from boto import ec2
import boto.ec2.elb
from boto.ec2.image import Image

myopts, args = getopt.getopt(sys.argv[1:],"d:p:t:m:")
usage = "Usage: %s -d [String. Config file directory path] -p [String. Production load balancer name] -t [Integer. Total number of instanced to produce. Optional - default 2] -m [Integer. Timeout in minutes for each step. Optional - default 5]" % sys.argv[0]

total_instances = 2
minutes = 5

if len(sys.argv) < 5:
    print(usage)
    sys.exit(1)

for o, a in myopts:
    if o == '-d':
        configPath = a 
    elif o == '-p':
        lb_name = a 
    elif o == '-t':
        total_instances = int(a)
    elif o == '-m':
        minutes = int(a) 
    else:
        print(usage)
        sys.exit(1)

# Definitions 
config = {}
execfile(configPath + "/deploy.conf", config)
ACCESS_KEY_ID = config["ACCESS_KEY_ID"]
SECRET_ACCESS_KEY =  config["SECRET_ACCESS_KEY"]
REGION =  config["REGION"]
STAGER_ID = config["STAGER_ID"]
INSTANCE_TYPE = config["INSTANCE_TYPE"]
SECURITY_GROUP = config["SECURITY_GROUP"]
KEY_PAIR = config["KEY_PAIR"]
BASE_PATH = config["BASE_PATH"]

timeout = time.time() + (60 * minutes)
base = 10 

logging.basicConfig(filename= BASE_PATH + 'deploy.log',level=logging.INFO) # use DEBUG for full report

conn = boto.ec2.connect_to_region(REGION, aws_access_key_id=ACCESS_KEY_ID, aws_secret_access_key=SECRET_ACCESS_KEY )
elb = boto.ec2.elb.connect_to_region(REGION, aws_access_key_id=ACCESS_KEY_ID, aws_secret_access_key=SECRET_ACCESS_KEY)


def trace(msg):
    print msg
    logging.info(msg)
    
def create_image(self, instance_id, name,
                     description=None,
                     no_reboot=True,
                     dry_run=False,
                     block_device_map=None):
    params = {
        'InstanceId': instance_id,
        'Name': name }
    if description:
        params[ 'Description' ] = description
    if no_reboot:
        params[ 'NoReboot' ] = 'true'
    if dry_run:
        params[ 'DryRun' ] = 'true'
    if block_device_map:
        block_device_map.ec2_build_list_params( params )
    img = self.get_object( 'CreateImage', params, Image, verb='POST' )
    return img.id

def create_AMI(new=True, instance_id=None):
    if new:
        instance_name = 'Deploy_' + str(time.strftime('%Y-%m-%d_%H-%M-%S',time.gmtime()))
        image_id = create_image(conn, STAGER_ID,instance_name)
    else:
        instance_name = 'Production_' + str(time.strftime('%Y-%m-%d_%H-%M-%S',time.gmtime()))
        image_id = create_image(conn, instance_id,instance_name)
    trace(image_id)
    return image_id

def getImageStatus(image_id):
    return conn.get_image(image_id).state

def getInstanceStatus(instance_id):
    return conn.get_all_instances(instance_ids=[instance_id])[0].instances[0].state

def waitAndReport(type,done,type_id,counter):
    counter = counter+1
    time.sleep(base)
    status = options[type](type_id)
    trace('%s %s status %s  ' % (type , str(type_id), status))
    if status == done:
        return
    elif status == 'failed':
        sys.exit(1)
    elif counter >= timeout/base:
        sys.exit(1)
    else:
        waitAndReport(type,done,type_id,counter)

def add_to_lb(load_balancer,instance_list):
    start = []
    counter = 0
    for instance_id in instance_list:
        load_balancer.register_instances(instance_id)
        trace('Adding %s to ELB %s' % (instance_id, load_balancer.name))
        start.append(time.time())
    for instance_id in instance_list:
        while True:
            health = load_balancer.get_instance_health([instance_id])[0]
            assert health.instance_id == instance_id
            assert time.time() < timeout
            if health.state == 'InService':
                trace('Instance %s now successfully InService in ELB %s (took %d seconds)' % (instance_id, load_balancer.name, time.time() - start[counter]))
                counter = counter +1
                break
            time.sleep(1)

def remove_from_lb(load_balancer,instance_id):
    if instance_id in [i.id for i in load_balancer.instances]:
        load_balancer.deregister_instances(instance_id)
        trace('Removing %s from ELB %s' % (instance_id, load_balancer.name))
        while True:
            health = load_balancer.get_instance_health([instance_id])[0]
            assert health.instance_id == instance_id
            assert time.time() < timeout
            if health.state == 'OutOfService':
                break
            trace('Waiting for removal...')
            time.sleep(1)

# Main
try:
    trace('\n\n\n----------------------------------------------------')
    trace('Script started @ ' + str(time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())))
    
    instance_list = []
    new_instance_list = []
    options = {'Image' : getImageStatus,
           'Instance' : getInstanceStatus,
    }

    # Get old images from load balancer
    load_balancer = elb.get_all_load_balancers([lb_name])[0]
    for instance_info in load_balancer.instances:
        if instance_info != None:
            print instance_info.id
            instance_list.append(str(instance_info.id))
            
    try:
        trace(load_balancer)
    except Exception,e:
        print e
        sys.exit(1)

    # Create AMI from stager
    image_id = create_AMI()
    waitAndReport('Image','available',image_id,0)

    trace("Currently running instances:")
    trace(instance_list)

    #Create instances from AMI
    for x in range(0, total_instances):
        new_instance = conn.run_instances(
                    image_id,
                    key_name=KEY_PAIR,
                    instance_type=INSTANCE_TYPE,
                    security_groups=[SECURITY_GROUP])
        new_instance_list.append(str(new_instance.instances[0].id))
        waitAndReport('Instance','running',new_instance.instances[0].id,0)

    trace("Newly created instances:")
    trace(new_instance_list)
    
    
    add_to_lb(load_balancer,new_instance_list)

    for instance_info in instance_list:
        remove_from_lb(load_balancer,instance_info)

    # Create AMI from production instance
    trace('Create ami from production instance')
    image_id = create_AMI(False, instance_list[0])
    waitAndReport('Image','available',image_id,0)
    for instance_info in instance_list:
        trace("Terminate %s " % (str(instance_info)))
        conn.terminate_instances(instance_ids=[instance_info])

    trace('Script ended @ ' + str(time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())))
    trace('Complete')
    
except Exception,e:
    trace(e)
    trace('Failure')
    
    

