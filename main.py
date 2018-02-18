######################
### LOAD LIBS AND GLOBALS ###
######################

import importlib
import os
#import settings
import sys
import time

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
THIRTYBIRDS_PATH = "%s/thirtybirds_2_0" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

from thirtybirds_2_0.Adaptors.Actuators import stepper_pulses

def left_wheel_callback():
    print "left_wheel_callback"




stepper_motor_channels = [
    {
        "name":"left_wheel",
        "pulse_pin":26,
        "dir_pin":6,
        "base_pulse_period":0.0005,
        "steps_finished_callback":left_wheel_callback,
        "backwards_orientation":False,
    }
]

stepper_pulses.init(stepper_motor_channels)


stepper_pulses.set("left_wheel", "speed", 1.0)
stepper_pulses.set("left_wheel", "steps", 800)
stepper_pulses.set("left_wheel", "speed", -1.0)
stepper_pulses.set("left_wheel", "steps", 800)
