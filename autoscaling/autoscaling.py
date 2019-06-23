import logging
import sys

import boto3

logging.basicConfig(level=logging.INFO)


# Helper class for Launch Configurations
class Autoscaling:

    # Contains instances in an autoscaling group
    instances = []

    def __init__(self, region, ami_id, config):
        self.client = boto3.client("autoscaling", region_name=region)
        self.ami_id = ami_id
        self.config = config

    # Update autoscaling group by creating a new launch configuration and adding to autoscaling group
    def update_autoscaling_group(self):
        self.__check_launch_configuration_exists()

        logging.info(
            "*** Creating new launch configuration {} ***".format(self.config.get("launch_configuration_name")))
        try:
            self.client.create_launch_configuration(
                LaunchConfigurationName=self.config.get("launch_configuration_name"),
                ImageId=self.ami_id,
                KeyName=self.config.get("ssh-key"),
                SecurityGroups=self.config.get("security-group-id"),
                InstanceType=self.config.get("instance-type"),
                AssociatePublicIpAddress=True
            )

            logging.info("*** Launch configuration created ***")

            self.__disable_metrics_collection()
            self.__check_autoscaling_group_exists()

            logging.info("*** Updating Autoscaling group with new Launch Configuration ***")

            self.client.update_auto_scaling_group(
                AutoScalingGroupName=self.config.get("autoscaling_group_name"),
                LaunchConfigurationName=self.config.get("launch_configuration_name")
            )

            logging.info("*** Autoscaling group is updated with new launch configuration ***")

            self.__enable_metrics_collection()

        except Exception as e:
            logging.error(e)
            sys.exit(1)

    # Checks if a launch configuration with the name already exists. If LC with the same name exists, the script will
    # stop and new name must be specified
    def __check_launch_configuration_exists(self):
        logging.info(
            "*** Checking if launch configuration {} exists ***".format(self.config.get("launch_configuration_name")))
        try:
            response = self.client.describe_launch_configurations(
                LaunchConfigurationNames=[
                    self.config.get("launch_configuration_name")
                ]
            )

            if len(response.get("LaunchConfigurations")) > 0:
                logging.warning(
                    "*** Launch Configuration {} exists ***".format(self.config.get("launch_configuration_name")))
                sys.exit(1)

        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Checks if autoscaling group exists or not. If does not exist, the script will stop
    def __check_autoscaling_group_exists(self):
        logging.info(
            "*** Checking if autoscaling group {} exists ***".format(self.config.get("autoscaling_group_name")))

        try:
            response = self.client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[
                    self.config.get("autoscaling_group_name")
                ]
            )

            if len(response.get("AutoScalingGroups")) == 0:
                logging.warning(
                    "*** Autoscaling Group {} does not exists ***".format(self.config.get("autoscaling_group_name")))
                sys.exit(1)

            logging.info("*** Autoscaling Group {} exists ***".format(self.config.get("autoscaling_group_name")))

            # Retrieving instances in ASG
            for instance in response.get("AutoScalingGroups")[0].get("Instances"):
                self.instances.append(instance.get("InstanceId"))

        except Exception as e:
            logging.error("*** {} ***".format(e))
            sys.exit(1)

    # Disables Metrics collection for Autoscaling group to update launch configuration
    def __disable_metrics_collection(self):
        logging.info(
            "*** Disabling metrics for {} autoscaling group ***".format(self.config.get("autoscaling_group_name")))

        try:
            self.client.disable_metrics_collection(
                AutoScalingGroupName=self.config.get("autoscaling_group_name")
            )

        except Exception as e:
            logging.error("*** Unable to disable metrics for {}: Cause {} ***"
                          .format(self.config.get("autoscaling_group_name"),
                                  e))
            sys.exit(1)

    # Enables Metrics collection for Autoscaling group to update launch configuration
    def __enable_metrics_collection(self):
        logging.info(
            "*** Enabling metrics for {} autoscaling group ***".format(self.config.get("autoscaling_group_name")))

        try:
            self.client.enable_metrics_collection(
                AutoScalingGroupName=self.config.get("autoscaling_group_name"),
                Granularity="1Minute"
            )

        except Exception as e:
            logging.error("*** Unable to enable metrics for {}: Cause {} ***"
                          .format(self.config.get("autoscaling_group_name"), e)
                          )
            sys.exit(1)

    def get_asg(self):
        self.__check_autoscaling_group_exists()
        print(self.instances)