import logging
import sys

import boto3

logging.basicConfig(level=logging.INFO)


class EC2:
    instances = []
    elb_subnets = []

    def __init__(self, region, ami, config):
        self.ec2_client = boto3.client("ec2", region_name=region)
        self.elb_client = boto3.client("elbv2", region_name=region)
        self.config = config
        self.ami = ami

    # Get the subnet ids for elb
    def _get_elb_subnets(self):
        try:
            response = self.elb_client.describe_load_balancers(
                LoadBalancerArns=[
                    self.config.get("loadbalancer").get("arn")
                ]
            )

            for subnet in response.get("LoadBalancers")[0].get("AvailabilityZones"):
                self.elb_subnets.append(subnet.get("SubnetId"))

        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Waiter to wait until instance is terminated
    def _instance_termination_waiter(self, instance_id):
        try:
            ec2_waiter = self.ec2_client.get_waiter('instance_terminated')
            ec2_waiter.wait(
                InstanceIds=[
                    instance_id
                ],
                WaiterConfig={
                    'Delay': 10
                }
            )
        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Waiter to wait until instance is created
    def _instance_running_waiter(self, instance_id):
        try:
            ec2_waiter = self.ec2_client.get_waiter('instance_running')
            ec2_waiter.wait(
                InstanceIds=[
                    instance_id
                ],
                WaiterConfig={
                    'Delay': 10
                }
            )
        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Waiter to wait until instance status check passes
    def _instance_status_check_waiter(self, instance_id):
        try:
            ec2_waiter = self.ec2_client.get_waiter('instance_status_ok')
            ec2_waiter.wait(
                InstanceIds=[
                    instance_id
                ],
                WaiterConfig={
                    'Delay': 10
                }
            )
        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Waiter to wait until system status check passes
    def _system_status_check_waiter(self, instance_id):
        try:
            ec2_waiter = self.ec2_client.get_waiter('system_status_ok')
            ec2_waiter.wait(
                InstanceIds=[
                    instance_id
                ],
                WaiterConfig={
                    'Delay': 10
                }
            )
        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Get instances in a target group
    def _get_elb_targets(self):
        try:
            response = self.elb_client.describe_target_health(
                TargetGroupArn=self.config.get("target-group").get("arn")
            )

            # Exit if no targets are found
            if len(response.get("TargetHealthDescriptions")) == 0:
                logging.error("*** No instances found in target group ***")
                sys.exit(1)

            for target in response.get("TargetHealthDescriptions"):
                self.instances.append(target.get("Target").get("Id"))

        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Describe target group health
    def _target_health_waiter(self, instance_id):
        try:
            waiter = self.elb_client.get_waiter('target_in_service')
            waiter.wait(
                TargetGroupArn=self.config.get("target-group").get("arn"),
                Targets=[
                    {
                        'Id': instance_id,
                        'Port': 80
                    },
                ],
                WaiterConfig={
                    'Delay': 10
                }
            )
        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Registers instance to elb
    def _register_instance_to_elb(self, instance_id):
        try:
            self.elb_client.register_targets(
                TargetGroupArn=self.config.get("target-group").get("arn"),
                Targets=[
                    {
                        'Id': instance_id,
                        'Port': 80
                    },
                ]
            )
        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Starts Rolling update
    def start_rolling_update(self):
        try:
            self._get_elb_targets()
            self._get_elb_subnets()

            # Script will exit if there are no instances in target group
            if len(self.instances) == 0:
                logging.error("*** Target group is empty ***")
                sys.exit(1)

            logging.info("*** Rolling update started ***")
            for old_instance in self.instances:

                # Create a instance
                logging.info("*** Launching a new instance ***")
                response = self.ec2_client.run_instances(
                    ImageId=self.ami,
                    InstanceType=self.config.get("instance-type"),
                    KeyName=self.config.get("ssh-key"),
                    MaxCount=1,
                    MinCount=1,
                    SecurityGroupIds=self.config.get("security-group-id"),
                    SubnetId=self.elb_subnets[self.instances.index(old_instance) % len(self.elb_subnets)],
                    TagSpecifications=[
                        {
                            "ResourceType": "instance",
                            "Tags": [
                                {
                                    "Key": "Name",
                                    "Value": self.config.get("version")
                                }
                            ]

                        },
                        {
                            "ResourceType": "volume",
                            "Tags": [
                                {
                                    "Key": "Name",
                                    "Value": self.config.get("version")
                                }
                            ]

                        }
                    ]
                )

                instance_id = response.get("Instances")[0].get("InstanceId")

                logging.info("*** Waiting for instance to run ***")
                self._instance_running_waiter(instance_id)

                logging.info("*** Waiting for instance and system status checks to pass ***")
                self._instance_status_check_waiter(instance_id)
                self._system_status_check_waiter(instance_id)

                logging.info("*** Register instance to ELB ***")
                self._register_instance_to_elb(instance_id)

                logging.info("*** Waiting for health check to pass")
                self._target_health_waiter(instance_id)

                logging.info("*** Terminating instance {} ***".format(old_instance))
                self.ec2_client.terminate_instances(
                    InstanceIds=[
                        old_instance
                    ]
                )

                self._instance_termination_waiter(old_instance)
                logging.info("*** Instance {} terminated ***".format(old_instance))

            logging.info("*** Rolling update completed ***")
        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Starts Rolling update
    # def start_rolling_update_with_asg(self):
    #
    #     try:
    #         # Script will exit if there are no instances in autoscaling group
    #         if len(self.instances) == 0:
    #             logging.error("*** Autoscaling group is empty ***")
    #             sys.exit(1)
    #
    #         logging.info("*** Rolling update started ***")
    #         # Deletes instance one by one
    #         for instance_id in self.instances:
    #
    #             logging.info("*** Terminating instance {} ***".format(instance_id))
    #             self.ec2_client.terminate_instances(
    #                 InstanceIds=[
    #                     instance_id
    #                 ]
    #             )
    #             self._instance_termination_waiter(instance_id)
    #             logging.info("*** Instance {} terminated ***".format(instance_id))
    #
    #             logging.info("*** Waiting for health check of new instance to pass ***")
    #             self.__target_health_waiter(instance_id)
    #             logging.info("*** Health check of new instance passed ***")
    #
    #             logging.info("*** Launching new instance ***")
    #
    #         logging.info("*** Rolling update completed ***")
    #     except Exception as e:
    #         logging.error("*** {} ***".format(e))
    #         sys.exit(1)
