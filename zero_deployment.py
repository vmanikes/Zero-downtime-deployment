import json
import sys
import logging
import argparse

from ec2.ec2 import EC2

parser = argparse.ArgumentParser()

parser.add_argument("new_ami", help="new ami id")
args = parser.parse_args()

try:
    with open("config.json", "r") as config_file:
        config = json.loads(config_file.read())
except FileNotFoundError:
    logging.error("config.json not in current directory")
    sys.exit(1)


rolling_update = EC2(config.get("region"), args.new_ami, config)
rolling_update.start_rolling_update()
