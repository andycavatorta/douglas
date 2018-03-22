######################
### LOAD LIBS AND GLOBALS ###
######################

print "starting"

import importlib
import json
import os
import math
import settings
import sys
import time

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
THIRTYBIRDS_PATH = "%s/thirtybirds_2_0" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

from thirtybirds_2_0.Network.info import init as network_info_init

print "imports finished"

network_info = network_info_init()
args = sys.argv # Could you actually get anything to happen without this?

def get_hostname():
    global args
    try:
        pos = args.index("-n") # pull hostname from command line argument, if there is one
        hostname = args[pos+1]
    except Exception as E:
        hostname = network_info.getHostName()
    return hostname

HOSTNAME = get_hostname()

print "hostname = {}".format(HOSTNAME)

####################
### PAUSE UNTIL ONLINE  ###
####################

PAUSE_UNTIL_ONLINE_MAX_SECONDS = 30

def pause_until_online(max_seconds):
    for x in range(max_seconds):
        if network_info.getOnlineStatus():
            print "got connection!"
            break
        else:
            print "waiting for connection..."
            time.sleep(1)

pause_until_online(PAUSE_UNTIL_ONLINE_MAX_SECONDS)

print "online"

#########################
### LOAD DEVICE-SPECIFIC CODE ###
#########################

print HOSTNAME, settings.server_names

if HOSTNAME in settings.bot_names:
    role = "bot"

elif HOSTNAME in settings.server_names:
    role = "controller"

elif HOSTNAME in settings.dashboard_names:
    role = "dashboard"


print "role = {}".format(role)

host = importlib.import_module("Roles.%s.main" % (role))
client = host.init(HOSTNAME)

