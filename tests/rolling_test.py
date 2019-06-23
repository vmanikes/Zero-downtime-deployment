import unittest
import json
import logging
import sys
from datetime import datetime

from botocore.stub import Stubber

from ec2.ec2 import EC2

logger = logging.getLogger()
logger.disabled = True


class TestELBMethods(unittest.TestCase):

    def setUp(self) -> None:
        try:
            with open("config.json", "r") as config_file:
                self.config = json.loads(config_file.read())
        except FileNotFoundError:
            logging.error("config.json not not found")
            sys.exit(1)

        self.rolling_update = EC2(self.config.get("region"), "ami-abcd1234", self.config)

    def test_get_elb_subnets(self):
        stubber = Stubber(self.rolling_update.elb_client)

        response = {
            'LoadBalancers': [
                {
                    'LoadBalancerArn': 'string',
                    'DNSName': 'string',
                    'CanonicalHostedZoneId': 'string',
                    'CreatedTime': datetime(2015, 1, 1),
                    'LoadBalancerName': 'string',
                    'Scheme': 'internet-facing',
                    'VpcId': 'string',
                    'State': {
                        'Code': 'active',
                        'Reason': 'string'
                    },
                    'Type': 'application',
                    'AvailabilityZones': [
                        {
                            'ZoneName': 'string',
                            'SubnetId': 'subnet-1234',
                            'LoadBalancerAddresses': [
                                {
                                    'IpAddress': 'string',
                                    'AllocationId': 'string'
                                },
                            ]
                        },
                    ],
                    'SecurityGroups': [
                        'string',
                    ],
                    'IpAddressType': 'ipv4'
                },
            ],
            'NextMarker': 'string'
        }

        expected_params = {'LoadBalancerArns': [self.config.get("loadbalancer").get("arn")]}

        stubber.add_response('describe_load_balancers', response, expected_params)

        with stubber:
            self.rolling_update._get_elb_subnets()
            self.assertEqual(len(self.rolling_update.elb_subnets), 1)

    def test_get_elb_subnets_bad_loadbalancer_arn(self):
        self.config["loadbalancer"]["arn"] = "invalid arn"
        self.assertRaises(SystemExit, self.rolling_update._get_elb_subnets)


    def test_get_elb_targets(self):
        stubber = Stubber(self.rolling_update.elb_client)

        response = {
            'TargetHealthDescriptions': [
                {
                    'Target': {
                        'Id': 'i-121121212',
                        'Port': 80,
                        'AvailabilityZone': 'us-east-1'
                    },
                    'HealthCheckPort': '80',
                    'TargetHealth': {
                        'State': 'healthy'
                    }
                },
            ]
        }
        expected_params = {'TargetGroupArn': self.config.get("target-group").get("arn")}
        stubber.add_response('describe_target_health', response, expected_params)

        with stubber:
            self.rolling_update._get_elb_targets()
            self.assertEqual(len(self.rolling_update.instances), 1)

    def test_get_elb_targets_bad_target_group_arn(self):
        self.config["target-group"]["arn"] = "invalid arn"
        self.assertRaises(SystemExit, self.rolling_update._get_elb_targets)

    def test_register_instance_to_elb(self):
        stubber = Stubber(self.rolling_update.elb_client)

        response = {}
        expected_params = {'TargetGroupArn': self.config.get("target-group").get("arn"),
                           'Targets': [
                               {
                                   'Id': "i-123ers221",
                                   'Port': 80
                               }
                           ]}
        stubber.add_response('register_targets', response, expected_params)

        with stubber:
            self.rolling_update._register_instance_to_elb("i-123ers221")


if __name__ == '__main__':
    unittest.main()