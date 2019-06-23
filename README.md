# Zero downtime deployment

Project that demonstrates a sample setup to do zero downtime deployments on AWS

## Requirements
- python3
- pip3
- AWS access for EC2, ELB

## Existing Setup
This solution assumes the following setup displayed below is already configured and serving traffic in your AWS environment:

```
                         Users
                           |
                           | 
                        Route53
                           |
                           |
                      Load Balancer
                      /    |     \
                     /     |      \
                    /      |       \
                   AZ-1   AZ-2     AZ-3
                   |       |        |
                   |       |        |
                   EC2    EC2      EC2
```

**NOTE:** The above figure is just a hypothetical figure, this solution works for any number  of Availability zones and
any number of instances. The only  catch is that the instances must be attached to a load balancer within a target group.

## Desired Solution
My solution will replace the existing instances with the updated EC2 instances with new AMI in the process of Rolling Deployment.
Rolling Deployment means that instances are taken down one at a time until the desired state is achieved. More information
about rolling deployment can be found [here](https://searchitoperations.techtarget.com/definition/rolling-deployment)

## Why not Blue-Green deployment?
There are few use-cases why I did not choose blue-green deployment 
- Expensive to create a duplicate stack.
- Too easy to implement and not to challenging. If I did blue-green deployment, I just had to create a same setup as above,
and need to add an entry in Route53 and configure weights

What would have happened if I used blue-green:
- Less risky 
- Easy roll back by just changing the DNS entry to point to old ELB and relaunch failed environment


## Assumptions 
- I am using a JSON file for additional configurations and this is because if I just give the ami id, I can get the 
additional attributes such as security group id, key name, etc from an instance by default from describe_instances() api call,
but I felt that is not ideal because when new deployment happens we may  need to change Security Group, or old key may 
be lost so we specify new key name, etc. In this way  my code is more configurable to fit the needs
- I used IAM roles instead of Access and secret access keys
- The script will exit with status code 1 when there is a failure or exception and the reason will be mentioned on stdout
- I am assuming that instances in elb are healthy before rolling update, even if they are not, the rolling update will cause them to be 
healthy (Provided the AMI given as input is working fine)
- You are running application on Application loadbalancer with target group with appropriate healthchecks configured
- The health check path must be same for both the old and new application as this code is not changing the health check path,
of target group. For example, if your health check path configured is `/health` and in new AMI if this route does not exist,
rolling update will be eventually be successful, but your instances will be in `unhealthy state` as the route is missing
- Health check traffic is running on port 80
- No additional block devices are attached to instance
- No userdata is provided and no instance profile exists
- Default `waiting period` for each waiting task is `400 seconds`

## How the update happens?
- When the update starts, First a new instance is launched before terminating the old instance
- Script will wait for the instance to be in `Running` state, `Instance` and `Status` checks are passed
- We will now register the newly created instance to the target group and wait for its health checks to pass
- Once the health checks are passed, we will terminate the old instance and repeat this process until all old instances are
terminated and new onces are launched


## How to run?
- Make sure you have all the requirements from above
- Run the following command to install the python packages to run the setup
```bash
cd ZeroDowntimeDeployment
pip3 install -r requirements.txt
```
- Personally not a fan of exposing `Access` and `Secret Access Keys` in code and an avid user for `IAM roles`. I strongly suggest
that this code to be run from an EC2 instances that has IAM role to access EC2 and ELB resources (assuming that a CI tool
 like Jenkins will execute this setup)
- If you don't want to use roles, make sure you have credentials configured in `~/.aws/credentials`
- Build an AMI in AWS that will host the updated code that is configured to start on boot and note the AMI ID
- Once you have the AMI, open the `config.json` and update the following keys accordingly, all values are required
```
{
  "region": "",
  "ssh-key": "",
  "security-group-id": [
    ""
  ],
  "instance-type": "",
  "target-group": {
    "arn": ""
  },
  "loadbalancer": {
    "arn": ""
  },
  "version": ""
}
```
- Run the following command to start rolling deployment `python3 zero_deployment.py {AMI_ID}`, Replace {AMI_ID} with your 
AMI_ID from above, Once the script starts the output will be something like below
```
INFO:root:*** Rolling update started ***
INFO:root:*** Launching a new instance ***
INFO:root:*** Waiting for instance to run ***
INFO:root:*** Waiting for instance and system status checks to pass ***
INFO:root:*** Register instance to ELB ***
INFO:root:*** Waiting or health check to pass
INFO:root:*** Terminating instance i-xxxxxxxxx ***
INFO:root:*** Instance i-xxxxxxxxx terminated ***
INFO:root:*** Launching a new instance ***
INFO:root:*** Waiting for instance to run ***
INFO:root:*** Waiting for instance and system status checks to pass ***
INFO:root:*** Register instance to ELB ***
INFO:root:*** Waiting for health check to pass
INFO:root:*** Terminating instance i-xxxxxxxxx ***
INFO:root:*** Instance i-xxxxxxxxx terminated ***
INFO:root:*** Rolling update completed ***
```

## How to run tests?
`python3 -m unittest tests/rolling_test.py`






