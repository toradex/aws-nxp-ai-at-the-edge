#
# Copyright 2019 Toradex AG. or its affiliates. All Rights Reserved.
#

# greengrass
import greengrasssdk
import platform

# rest consume
import requests

# mqtt thread
import threading
import time
import json
from utils import Utils

# Creating a greengrass core sdk client
client = greengrasssdk.client('iot-data')
# Retrieving platform information to send from Greengrass Core
my_platform = platform.platform()
# utils methods
util = Utils()

# "THREAD" for MQTT connections
def greengrass_mqtt_run():
	while True:
		# cpu/data
		cpuData = requests.get("http://localhost:5001/cpu")
		client.publish(topic='cpu/data', payload=cpuData)
		print("Mqtt cpu/data published ...")
		# gpu/data
		gpuData = requests.get("http://localhost:5001/gpu")
		client.publish(topic='gpu/data', payload=gpuData)
		print("Mqtt gpu/data published ...")
		# ram/data
		ramData = requests.get("http://localhost:5001/ram")
		client.publish(topic='ram/data', payload=ramData)
		print("Mqtt ram/data published ...")
		time.sleep(5)

t = threading.Thread(target=greengrass_mqtt_run)
t.start()

# This is a dummy handler and will not be invoked
# Instead the code above will be executed in an infinite loop for our example
def function_handler(event, context):
	return
