#!/usr/bin/env python3

import sys
import os

folder = os.path.dirname(os.path.abspath(__file__))  # noqa
sys.path.insert(0, os.path.normpath("%s/.." % folder))  # noqa

from pytradfri import Gateway
from pytradfri.api.libcoap_api import APIFactory
from pytradfri.error import PytradfriError
from pytradfri.util import load_json, save_json

import uuid
import argparse
import threading
import time
import json

def save_dict(filename, d):
	json.dump(d, open(filename, 'w'))

def load_dict(filename):
	try:
		return json.load(open(filename, 'r'))
	except FileNotFoundError:
		return {}
	

CONFIG_FILE = '/home/vvdveen/tradfri_standalone_psk.conf'
POWER_STATUS_FILE = '/home/vvdveen/tradfri_power_status.conf'
IP = '10.0.0.109'

if IP not in load_json(CONFIG_FILE):
	raise PytradfriError("Lost Gateway")

conf = load_json(CONFIG_FILE)
try:
	identity = conf[IP].get('identity')
	psk = conf[IP].get('key')
	api_factory = APIFactory(host=IP, psk_id=identity, psk=psk)
except KeyError:
	raise PytradfriError("Lost Gateway")

api = api_factory.request

gateway = Gateway()

devices_command = gateway.get_devices()
devices_commands = api(devices_command)
devices = api(devices_commands)
lights = [ dev for dev in devices if dev.has_light_control ]
print("Gateway reports {} lights".format(len(lights)))

unreachable_count = load_dict(POWER_STATUS_FILE)
print("Database reports {} lights".format(len(unreachable_count)))

if len(unreachable_count) != len(lights):
	unreachable_count = {}

	for light in lights:
		unreachable_count[light.name] = 0

	save_dict(POWER_STATUS_FILE, unreachable_count)


db_needs_update = False

# First, send the same dimmer value to each bulb that is supposedly reachable
print("")
for light in lights:
	dim_level = light.light_control.lights[0].dimmer
	dim_command = light.light_control.set_dimmer(dim_level)
	api(dim_command)

	print("Bulb {}:".format(light.name))
	print("- state: {}".format(light.light_control.lights[0].state))
	print("- dimmer: {}".format(light.light_control.lights[0].dimmer))
	print("- unreachable_count: {}".format(unreachable_count[light.name]))

# New state | Previous state | Action
# ----------+----------------+-------------
# power on  | power on       | -
# power on  | power off      | update previous state + reset dim level
# power off | power on       | update previous state
# power off | power off      | -

	if light.reachable and unreachable_count[light.name]:
		# Reachable again

 		if unreachable_count[light.name] >= 3:
			# Reachable again after a 'long' time

			print("Bulb {} is reachable again after some time! Was it powered on?".format(light.name))
			dim_level = 254
			dim_command = light.light_control.set_dimmer(dim_level)
			api(dim_command)

		unreachable_count[light.name] = 0 
		db_needs_update = True
			

	elif not light.reachable and unreachable_count[light.name] < 5:
		# Not reachable, but we have seen it recently

		unreachable_count[light.name] += 1
		db_needs_update = True

		print("Bulb {} has been unreachable {} times".format(light.name,unreachable_count[light.name]))


if db_needs_update:
	print("Writing database to disk")
	save_json(POWER_STATUS_FILE, unreachable_count)






print("Bye")
print("")
