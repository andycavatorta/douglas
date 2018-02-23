######################
### LOAD LIBS AND GLOBALS ###
######################

import importlib
import os
import math
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

def right_wheel_callback():
    print "right_wheel_callback"

stepper_motor_channels = [
    {
        "name":"left_wheel",
        "pulse_pin":26,
        "dir_pin":6,
        "base_pulse_period":0.0005,
        "steps_finished_callback":left_wheel_callback,
        "backwards_orientation":False,
    },
    {
        "name":"right_wheel",
        "pulse_pin":21,
        "dir_pin":20,
        "base_pulse_period":0.0005,
        "steps_finished_callback":right_wheel_callback,
        "backwards_orientation":True,
    }
]

stepper_pulses.init(stepper_motor_channels)

class Vectors_To_Pulses(object):
    def __init__(self, wheel_circumference, distance_between_wheels, steps_per_rotation):
        self.wheel_circumference = wheel_circumference
        self.distance_between_wheels = distance_between_wheels
        self.steps_per_rotation = steps_per_rotation
        self.circumference_of_rotation = self.distance_between_wheels * math.pi
        self.speed = 0.0

    def rotate(self, degrees, speed = self.speed):
        self.speed = Float(abs(speed))
        proportion_of_circle = Float(abs(degrees)) / 360.0
        length_of_arc = proportion_of_circle * self.circumference_of_rotation
        pulses_of_arc = length_of_arc * self.steps_per_rotation
        left_speed, right_speed = speed, -speed if degrees > 0 else -speed, speed
        return {
            "left_wheel":{
                "speed":left_speed, 
                "steps":pulses_of_arc
            },
            "right_wheel":{
                "speed":right_speed, 
                "steps":pulses_of_arc
            }
        }

    def roll(self, distance, speed = self.speed): # distance units are in mm
        self.speed = Float(abs(speed)) if distance > 0 else Float(abs(-speed))
        number_of_wheel_rotations = abs(distance) / self.wheel_circumference
        number_of_pulses = number_of_wheel_rotations * self.steps_per_rotation
        return {
            "left_wheel":{
                "speed":self.speed, 
                "steps":number_of_pulses
            },
            "right_wheel":{
                "speed":self.speed, 
                "steps":number_of_pulses
            }
        }


"""
vectors_to_pulses = Vectors_To_Pulses(25.4 * math.pi, 215.0, 1600)
    pulse_info = vectors_to_pulses.rotate(360, 1)
    stepper_pulses.set("left_wheel", "speed", pulse_info["left_wheel"]["speed"])
    stepper_pulses.set("left_wheel", "steps", pulse_info["left_wheel"]["steps"])
    stepper_pulses.set("right_wheel", "speed", pulse_info["right_wheel"]["speed"])
    stepper_pulses.set("right_wheel", "steps", pulse_info["right_wheel"]["steps"])

stepper_pulses.set("left_wheel", "speed", -1.0)
stepper_pulses.set("right_wheel", "speed", -1.0)
stepper_pulses.set("left_wheel", "steps", 10000)
stepper_pulses.set("right_wheel", "steps", 10000)
"""

class Path_Collection(object):
    def __init__(self):
        self.path_cursor = 0
        self.path_collection = []
    def load_path_collection(self, path_collection):
        self.rewind_path_cursor()
        self.path_collection = path_collection
    def rewind_path_cursor(self, cursor = 0):
        self.path_cursor = cursor
    def get_next_path(self):
        self.path_cursor += 1
        if self.path_cursor < len(self.path_collection):
            return self.path_collection[self.path_cursor]
        else:
            return False

class Coordinates_To_Vectors(object):
    def __init__(self):
        self.current_x = 0
        self.current_y = 0
        self.current_orientation = 0
        self.target_x = 0
        self.target_y = 0
        self.target_orientation = 0

    def update_coordinates_from_reckoning(self):
        self.current_x = self.target_x
        self.current_y = self.target_y
        self.current_orientation = self.target_orientation

    def update_coordinates_from_lps(self, x, y, orientation):
        error = [self.current_x - x, self.current_y - y, self.current_orientation - orientation]
        self.current_x = x
        self.current_y = y
        self.current_orientation = orientation
        print "Coordinates_To_Vectors.set_current_coordinates error=", error
        return error

    def calculate_vectors_from_target_coordinates(self, target_x, target_y):
        # calculate distance
        distance = math.sqrt(((self.current_x - target_x)**2) + ((self.current_y - target_y)**2))
        # calculate absolute heading relative to Cartesian space, not relative to bot
        if self.current_x == target_x and self.current_y == target_y: # no movement
            return (0.0, 0.0)
        elif self.current_x < target_x and self.current_y == target_y: # x-axis positive
            return (distance, 0.0)
        elif self.current_x > target_x and self.current_y == target_y:: # x-axis negative
            return (distance, 180.0)
        elif self.current_x == target_x and self.current_y < target_y: # y-axis positive
            return (distance, 90.0)
        elif self.current_x == target_x and self.current_y > target_y: # y-axis negative
            return (distance, -90.0)
        elif self.current_x < target_x and self.current_y < target_y: # somewhere in quadrant 1
            target_angle_relative_to_Cartesian_space =  math.degrees(math.acos( abs(target_x-self.current_x) / distance) )
            return (distance, target_angle_relative_to_Cartesian_space)
        elif self.current_x > target_x and self.current_y < target_y: # somewhere in quadrant 2
            target_angle_relative_to_Cartesian_space =  90 + math.degrees(math.acos( abs(target_x-self.current_x) / distance) )
            return (distance, target_angle_relative_to_Cartesian_space)
        elif self.current_x > target_x and self.current_y > target_y: # somewhere in quadrant 3
            target_angle_relative_to_Cartesian_space =  180 + math.degrees(math.acos( abs(target_x-self.current_x) / distance) )
            return (distance, target_angle_relative_to_Cartesian_space)
        elif self.current_x < target_x and self.current_y > target_y: # somewhere in quadrant 4
            target_angle_relative_to_Cartesian_space =  270 + math.degrees(math.acos( abs(target_x-self.current_x) / distance) )
            return (distance, target_angle_relative_to_Cartesian_space)
        elif :
            print "Coordinates_To_Vectors.calculate_vectors_from_target_coordinates cannot assign quadrant", self.current_x, target_x, self.current_y, target_y

    def convert(self, target_x, target_y):
        target_distance, target_angle_relative_to_Cartesian_space = self.calculate_vectors_from_target_coordinates(target_x, target_y)
        target_angle_relative_to_bot = target_angle_relative_to_Cartesian_space - self.current_orientation
        self.target_orientation = target_angle_relative_to_Cartesian_space
        self.target_x = target_x
        self.target_y = target_y
        return target_distance, target_angle_relative_to_bot


