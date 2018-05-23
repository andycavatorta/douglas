"""
spatial representation systems:

coordinates_from_touch_designer
pixel_space_from_camera_lps
physical_space_from_lps (physical_hw_of_canvas(0,0), pixel_space_coordinates_of_corners([0,0],[0,0],[0,0],[0,0]))
physical_space_coordinates_of_marker 
physical_space_coordinates_of_brush 
vector_space_of_path
vector_space_of_odometry 



"""
######################
### LOAD LIBS AND GLOBALS ###
######################

import importlib
import json
import os
import math
import settings
import sys
import time

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
#THIRTYBIRDS_PATH = "%s/thirtybirds_2_0" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

from thirtybirds_2_0.Network.info import init as network_info_init


network_info = network_info_init()
args = sys.argv 

try:
    hostname = args[args.index("-hostname")+1] # pull hostname from command line argument, if there is one
except Exception as E:
    hostname = network_info.getHostName()

#print "hostname = {}".format(hostname)

####################
### PAUSE UNTIL ONLINE  ###
####################

PAUSE_UNTIL_ONLINE_MAX_SECONDS = 30

def pause_until_online(max_seconds):
    for x in range(max_seconds):
        if network_info.getOnlineStatus():
            print "connected to Internet"
            break
        else:
            print "waiting for connection to Internet..."
            time.sleep(1)

pause_until_online(PAUSE_UNTIL_ONLINE_MAX_SECONDS)

#########################
### LOAD DEVICE-SPECIFIC CODE ###
#########################

if hostname in settings.bot_names:
    role = "bot"

elif hostname in settings.server_names:
    role = "controller"

elif hostname in settings.dashboard_names:
    role = "dashboard"

if role == "controller":
    try:
        canvas_size = args[args.index("-canvas_size")+1] # pull hostname from command line argument, if there is one
    except Exception as E:
        print "please specify the canvas_size using form 'python main.py -canvas_size <canvas size in meters>'"
        sys.exit()

    try:
        drawing_name = args[args.index("-drawing_name")+1] # pull hostname from command line argument, if there is one
    except Exception as E:
        print "please specify the drawing_name using form 'python main.py -drawing_name <drawing name without .json extention>'"
        sys.exit()

    try:
        lps_ip = args.index("-lps_ip") # pull hostname from command line argument, if there is one
    except Exception as E:
        lps_ip = False
        print "No ip address specified for LPS.  That's fine.  But if you want to use an LPS, please specify drawing_name in the form 'python main.py -drawing_name <filename> -lps_ip <ip address>'"
    host = importlib.import_module("Roles.%s.main" % (role))
    client = host.init(hostname, drawing_name, float(canvas_size), lps_ip)
else:
    host = importlib.import_module("Roles.%s.main" % (role))
    client = host.init(hostname)
