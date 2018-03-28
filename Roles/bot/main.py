"""
This control system is so




"""

import commands
import math
import os
import Queue
import settings
import time
import threading
import traceback
import sys

from thirtybirds_2_0.Network.manager import init as network_init
from thirtybirds_2_0.Updates.manager import init as updates_init
from thirtybirds_2_0.PiUtils.management import init as management_init
from thirtybirds_2_0.Adaptors.Actuators import stepper_pulses



class Motor_Control(threading.Thread):
    """
    This class receives basic motion commands and sends control messages to the motors.
    
    incoming message topics:
        speed(0.0-1.0)
        roll([-]meters)
        rotate([-]degrees)
        brush(["up"|"down"])
        enable ([True|False])

    outgoing message topics:
        rotate_progress([-]degrees)
        roll_progress([-]meters)
        brush_position(["up"|"down"])

    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.message_queue = Queue.Queue()
        self.command_queue = Queue.Queue()
        settings.motor_control["stepper_motors"]["left_wheel"]["status_callback"] = self.motor_callback
        settings.motor_control["stepper_motors"]["right_wheel"]["status_callback"] = self.motor_callback
        settings.motor_control["stepper_motors"]["brush_arm"]["status_callback"] = self.motor_callback
        
        stepper_pulses.init(settings.motor_control["stepper_motors"])
        self.distance_between_wheels = settings.motor_control["distance_between_wheels"] 
        self.steps_per_rotation = settings.motor_control["steps_per_rotation"] 
        self.wheel_circumference = settings.motor_control["wheel_circumference"] 
        self.circumference_of_rotation = self.distance_between_wheels * math.pi

        self.brush_position_up = False

        self.finished = {
            "left_wheel":True,
            "right_wheel":True,
            "brush_arm":True
        }
        self.pulse_odometer = {
            "left_wheel":0,
            "right_wheel":0,
            "brush_arm":0
        }

        stepper_pulses.set("left_wheel", "speed", 1.0)
        stepper_pulses.set("right_wheel", "speed", 1.0)
        stepper_pulses.set("brush_arm", "speed", 1.0)

        stepper_pulses.set("left_wheel", "enable", True)
        stepper_pulses.set("right_wheel", "enable", True)
        stepper_pulses.set("brush_arm", "enable", True)

    def rotate(self, degrees, speed):
        print "Motor_Control.rotate", degrees, speed
        self.speed = float(abs(speed))
        print "float(abs(degrees))", float(abs(degrees))
        proportion_of_circle = float(abs(degrees)) / 360.0
        print "proportion_of_circle", proportion_of_circle

        length_of_arc = proportion_of_circle * self.circumference_of_rotation
        print "length_of_arc", length_of_arc

        pulses_of_arc = length_of_arc * self.steps_per_rotation
        print "pulses_of_arc", pulses_of_arc
        left_steps, right_steps = (pulses_of_arc, -pulses_of_arc) if degrees > 0 else (-pulses_of_arc, pulses_of_arc)

        self.finished = {
            "left_wheel":False,
            "right_wheel":False,
            "brush_arm":False
        }
        self.pulse_odometer = {
            "left_wheel":0,
            "right_wheel":0,
            "brush_arm":0
        }

        stepper_pulses.set("left_wheel", "speed", speed)
        stepper_pulses.set("right_wheel", "speed", speed)
        stepper_pulses.set("brush_arm", "speed", speed)

        stepper_pulses.set("left_wheel", "steps", left_steps)
        stepper_pulses.set("right_wheel", "steps", right_steps)
        stepper_pulses.set("brush_arm", "steps", 0)

    def roll(self, distance, speed): # distance units are in mm
        print "Motor_Control.roll", distance, speed
        number_of_wheel_rotations = abs(distance) / self.wheel_circumference
        number_of_pulses = number_of_wheel_rotations * self.steps_per_rotation

        self.finished = {
            "left_wheel":False,
            "right_wheel":False,
            "brush_arm":False
        }
        self.pulse_odometer = {
            "left_wheel":0,
            "right_wheel":0,
            "brush_arm":0
        }

        left_steps, right_steps = (number_of_pulses, number_of_pulses) if distance > 0 else (-number_of_pulses, -number_of_pulses)

        stepper_pulses.set("left_wheel", "speed", speed)
        stepper_pulses.set("right_wheel", "speed", speed)
        stepper_pulses.set("brush_arm", "speed", speed)

        stepper_pulses.set("left_wheel", "steps", left_steps)
        stepper_pulses.set("right_wheel", "steps", right_steps)
        stepper_pulses.set("brush_arm", "steps", 0)

    def brush_arm(self, brush_position_up, speed): # distance units are in mm
        print "Motor_Control.brush_arm", brush_position_up, speed
        #number_of_wheel_rotations = abs(distance) / self.wheel_circumference

        if brush_position_up == self.brush_position_up: # if we're already in the right position
            return 

        self.brush_position_up = brush_position_up
        if self.brush_position_up:
            number_of_pulses = 300
        else: 
            number_of_pulses = -300

        #number_of_pulses = brush_position_up
        #number_of_pulses = settings.motor_control["stepper_motors"] if distance else -settings.motor_control["stepper_motors"]

        self.finished = {
            "left_wheel":False,
            "right_wheel":False,
            "brush_arm":False
        }
        self.pulse_odometer = {
            "left_wheel":0,
            "right_wheel":0,
            "brush_arm":0
        }

        stepper_pulses.set("left_wheel", "speed", speed)
        stepper_pulses.set("right_wheel", "speed", speed)
        stepper_pulses.set("brush_arm", "speed", speed)

        stepper_pulses.set("left_wheel", "steps", 0)
        stepper_pulses.set("right_wheel", "steps", 0)
        stepper_pulses.set("brush_arm", "steps", number_of_pulses)

    def motor_callback(self, motor_name, msg_type, data):
        
        if msg_type == "steps_cursor":
            if motor_name in ["left_wheel", "right_wheel"]:
                
                self.pulse_odometer[motor_name] = data # collect pulse odometer for each motor
                left_distance  = self.pulse_odometer["left_wheel"]  / float(self.steps_per_rotation) * self.wheel_circumference * ( 1 if settings.motor_control["stepper_motors"]["left_wheel"]["backwards_orientation"] else -1)
                right_distance = self.pulse_odometer["right_wheel"] / float(self.steps_per_rotation) * self.wheel_circumference * ( 1 if settings.motor_control["stepper_motors"]["right_wheel"]["backwards_orientation"] else -1)
                average_distance = (abs(left_distance) + abs(right_distance)) / 2.0
                if left_distance < 0 and right_distance > 0: # rotate left
                    proportion_of_circle = average_distance / self.circumference_of_rotation
                    degrees = proportion_of_circle * 360.0
                    #print "motor_callback", motor_name, msg_type, data, degrees
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["rotate", degrees]])
                    return
                if left_distance > 0 and right_distance < 0: # rotate right
                    proportion_of_circle = average_distance / self.circumference_of_rotation
                    degrees = proportion_of_circle * 360.0
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["rotate", -degrees]])
                    return
                if left_distance > 0 and right_distance > 0: # roll forward
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["roll", average_distance]])
                    return
                if left_distance < 0 and right_distance < 0: # roll backward
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["roll", -average_distance]])
                    return

        if msg_type == "finished":
            #print "motor_callback", motor_name, msg_type, data
            self.finished[motor_name] = data
            if self.finished["left_wheel"] and self.finished["right_wheel"] and self.finished["brush_arm"]:
                self.add_to_queue(["finished", None, None])
                

    def add_to_queue(self, msg):
        print "Motor_Control.add_to_queue", msg
        self.message_queue.put(msg)

    def run(self):
        while True:
            try:
                # block on waiting for all motors to acknowledge completion or disable
                command, value, speed = self.message_queue.get(True)
                print "Motor_Control.run", command, value, speed
                if command in ["rotate","roll","brush_arm"]:
                    self.command_queue.put([command, value, speed])
                if command == "enable":
                    stepper_pulses.set("left_wheel", "enable", value)
                    stepper_pulses.set("right_wheel", "enable", value)
                    stepper_pulses.set("brush_arm", "enable", value)
                if command == "finished":
                    try:
                        command, value, speed = self.command_queue.get(False)
                        if command  == "rotate":
                            self.rotate(value, speed)
                            return
                        if command  == "roll":
                            self.roll(value, speed)
                            return
                        if command  == "brush":
                            self.brush_arm(value, speed)
                            return
                    except Queue.Empty:
                        pass

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

motor_control = Motor_Control()
motor_control.daemon = True

class Spatial_Translation(threading.Thread):
    """
    This class translates between coordinates and vectors

    It also generates high-level commands for the motor controller [ roll(meters), rotate(degrees), brush(["up"|"down"]) ]

    incoming message topics:
        destination ( location["x"], location["y"], location["orientation"], destination_x, destination_y )
        enable ([True|False])

    outgoing message topics:
        location_from_odometry (location["x"], location["y"], location["orientation"])
        "spatial_translation>location_server.location_from_odometry"
    
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        #self.origin = None
        #self.destination = None
        #self.location_from_odometry = None

    def add_to_queue(self, msg):
        print "spatial_translation.add_to_queue", msg
        self.queue.put(msg)

    def translate_cartesian_to_vectors(self, origin, destination):
        # calculate distance
        origin_x, origin_y = origin # for simplicity
        destination_x, destination_y, brush = destination # for simplicity


        distance = math.sqrt(((origin_x - destination_x)**2) + ((origin_y - destination_y)**2))
        # calculate absolute heading relative to Cartesian space, not relative to bot
        if origin_x == destination_x and origin_y == destination_y: # no movement
            return (0.0, 0.0)
        elif origin_x < destination_x and origin_y == destination_y: # x-axis positive
            return (distance, 0.0)
        elif origin_x > destination_x and origin_y == destination_y: # x-axis negative
            return (distance, 180.0)
        elif origin_x == destination_x and origin_y < destination_y: # y-axis positive
            return (distance, 90.0)
        elif origin_x == destination_x and origin_y > destination_y: # y-axis negative
            return (distance, -90.0)
        elif origin_x < destination_x and origin_y < destination_y: # somewhere in quadrant 1
            target_angle_relative_to_Cartesian_space =  math.degrees(math.acos( abs(destination_x-origin_x) / distance) )
            target_angle_relative_to_bot = target_angle_relative_to_Cartesian_space - origin["orientation"]
            return (distance, target_angle_relative_to_bot)
        elif origin_x > destination_x and origin_y < destination_y: # somewhere in quadrant 2
            target_angle_relative_to_Cartesian_space =  90 + math.degrees(math.acos( abs(destination_x-origin_x) / distance) )
            target_angle_relative_to_bot = target_angle_relative_to_Cartesian_space - origin["orientation"]
            return (distance, target_angle_relative_to_bot)
        elif origin_x > destination_x and origin_y > destination_y: # somewhere in quadrant 3
            target_angle_relative_to_Cartesian_space =  180 + math.degrees(math.acos( abs(destination_x-origin_x) / distance) )
            target_angle_relative_to_bot = target_angle_relative_to_Cartesian_space - origin["orientation"]
            return (distance, target_angle_relative_to_bot)
        elif origin_x < destination_x and origin_y > destination_y: # somewhere in quadrant 4
            target_angle_relative_to_Cartesian_space =  270 + math.degrees(math.acos( abs(destination_x-origin_x) / distance) )
            target_angle_relative_to_bot = target_angle_relative_to_Cartesian_space - origin["orientation"]
            return (distance, target_angle_relative_to_bot)
        else :
            print "Coordinates_To_Vectors.calculate_vectors_from_target_coordinates cannot assign quadrant", origin_x, destination_x, origin_y, destination_y


    def translate_vectors_to_cartesian(self):
        return

    def translate_vectors_to_motor_commands(self, brush, distance, target_angle_relative_to_bot):
        motor_control.add_to_queue(["brush", brush, 1.0])
        motor_control.add_to_queue(["rotate", target_angle_relative_to_bot, 1.0])
        motor_control.add_to_queue(["roll", distance, 1.0])
        return

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                print "spatial_translation.run", topic, msg
                if topic == "mobility_loop>spatial_translation.set_destination":
                    origin, destination = msg
                    distance, target_angle_relative_to_bot = self.translate_cartesian_to_vectors(origin, destination)
                    brush = destination[2]
                    print "distance, target_angle_relative_to_bot", distance, target_angle_relative_to_bot
                    self.translate_vectors_to_motor_commands(brush, distance, target_angle_relative_to_bot)
                    continue

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

spatial_translation = Spatial_Translation()
spatial_translation.daemon = True

class Path_Server(threading.Thread):
    """
        This class manages the three types of paths []
        And it serves next destination

        incoming message topics:
            location_from_lps
            path_list
            path_to_reservoir
            "location_server>path_server.location_correction"
        outgoing message topics:
            destination
    
        synchronous functions:
            

    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.stroke_paths = []
        self.stroke_paths_cursor = 0
        self.paths_to_available_paint = []
        self.paths_to_available_paint_cursor = 0
        self.location_correction_paths = []
        self.location_correction_paths_cursor = 0
        self.outstanding_destination_request = False

    def request_paths_if_needed(self):
        if len(self.stroke_paths) == 0:
            network.send("path_server.stroke_paths_request", True)
            return True
        else:
            return False

    def generate_destination(self): # separated from run() for readability
        """
        if self.location_correction_paths_cursor < len(self.location_correction_paths):
            next_path = self.location_correction_paths[self.location_correction_paths_cursor]
            self.location_correction_paths_cursor += 1
            return next_path
        if self.paths_to_available_paint_cursor < len(self.paths_to_available_paint):
            next_path = self.paths_to_available_paint[self.paths_to_available_paint_cursor]
            self.paths_to_available_paint_cursor += 1
            return next_path
        """
        if self.stroke_paths_cursor < len(self.stroke_paths):
            next_path = self.stroke_paths[self.stroke_paths_cursor]
            self.stroke_paths_cursor += 1
            return next_path
        return None

    def add_to_queue(self, msg):
        self.queue.put(msg)

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                print "path_server.add_to_queue",topic, msg
                if topic == "path_server.stroke_paths_response":
                    self.stroke_paths = msg
                    self.stroke_paths_cursor = 0
                    #if self.outstanding_destination_request:
                    mobility_loop.add_to_queue(["path_server>mobility_loop.destination_response", self.generate_destination()])

                if topic == "location_server>path_server.location_correction_paths":
                    self.location_correction_paths = msg
                    self.location_correction_paths_cursor = 0

                if topic == "path_server.paths_to_available_paint_response":
                    self.paths_to_available_paint = msg
                    self.paths_to_available_paint_cursor = 0

                if topic == "mobility_loop>path_server.destination_request":
                    if self.stroke_paths == []: # if stroke_paths have not been received
                        self.outstanding_destination_request == True
                        network.send("path_server.stroke_paths_request", True)
                    else:
                        mobility_loop.add_to_queue("path_server>mobility_loop.destination_response", self.generate_destination())

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

path_server = Path_Server()
path_server.daemon = True



class Location_Server(threading.Thread):
    """
        This class tracks the current location and orientation using odometry from the Navigator and location data from the LPS 
        incoming message topics:
            location_from_lps
            location_from_odometry
        outgoing message topics:
            location_from_server
        synchronous functions:
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()

        self.location_from_odometry = {
            "x":0.0,
            "y":0.0,
            "orientation":0.0,
            "timestamp":None
        }
        self.location_from_lps = {
            "x":0.0,
            "y":0.0,
            "orientation":0.0,
            "timestamp":None
        }
        self.location_disparity_threshold = settings.location_server["location_disparity_threshold"]
        self.outstanding_location_request = False
        self.lps_data_is_fresh = False

    def detect_location_disparity(self):
        for key in ["x","y","orientation","timestamp"]:
            if abs(self.location_from_odometry[key] - self.location_from_lps[key]) > self.location_disparity_threshold[key]:
                return True
        return False

    def add_to_queue(self, msg):
        self.queue.put(msg)

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                #print topic, msg
                if topic == "location_server.location_from_lps_response":
                    self.location_from_lps["x"] = float(msg["x"])
                    self.location_from_lps["y"] = float(msg["y"])
                    self.location_from_lps["orientation"] = float(msg["orientation"])
                    self.location_from_lps["timestamp"] = time.time()
                    if self.location_from_odometry["timestamp"] is None: # self.location_from_odometry is not yet initialized
                        self.location_from_odometry["x"] = float(self.location_from_lps["x"])
                        self.location_from_odometry["y"] = float(self.location_from_lps["y"])
                        self.location_from_odometry["orientation"] = float(self.location_from_lps["orientation"])
                        self.location_from_odometry["timestamp"] = time.time()
                        if self.outstanding_location_request == True: # start up case
                            self.outstanding_location_request = False
                            mobility_loop.add_to_queue("location_server>mobility_loop.location_response", self.location_from_odometry)
                    if self.detect_location_disparity():
                        pass
                        # to do: figure out how to remedy disparities in all cases
                        # need to send correction info to path server "location_server>path_server.location_correction"
                        mobility_loop.add_to_queue("location_server>path_server.location_correction_paths", self.location_from_lps)

                if topic == "spatial_translation>location_server.location_from_odometry":
                    self.location_from_odometry["x"] = float(msg["x"])
                    self.location_from_odometry["y"] = float(msg["y"])
                    self.location_from_odometry["orientation"] = float(msg["orientation"])
                    self.location_from_odometry["timestamp"] = time.time()

                if topic == "motor_control>location_server.relative_odometry":
                    motion_type, distance = msg
                    if motion_type == "rotate":
                        self.location_from_odometry["orientation"] += distance
                    if motion_type == "roll":
                        self.location_from_odometry["x"] += distance * math.cos(math.radians(self.location_from_odometry["orientation"]))
                        self.location_from_odometry["y"] += math.sin(math.radians(self.location_from_odometry["orientation"]))
                
                if topic == "mobility_loop>location_server.location_request":
                    if self.lps_data_is_fresh:
                        pass
                    else: 
                        mobility_loop.add_to_queue("location_server>mobility_loop.location_response", self.location_from_odometry)
                    #if self.location_from_odometry["timestamp"] is None: # start up case
                    #    self.outstanding_location_request = True   
                    #else:
                    #    mobility_loop.add_to_queue("location_server>mobility_loop.location_response", self.location_from_odometry)

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

location_server = Location_Server()
location_server.daemon = True




class Mobility_Loop(threading.Thread):
    """
        This class 
        incoming message topics:
            "location_server>mobility_loop.location_response"
        outgoing message topics:
            "mobility_loop>location_server.location_request"
        synchronous functions:
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        #self.current_task = ["wait_for_location," "wait_for_destination","wait_for_lease","wait_for_motion"][0] # < options listed for you, dear programmer
        self.location = [0,0]
        self.destination =  None
        self.lease = None
        self.motion_complete = False

    def add_to_queue(self, msg):
        print "mobility_loop.add_to_queue", msg
        self.queue.put(msg)

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                #print topic, msg

                if topic == "location_server>mobility_loop.location_response":
                    self.location = msg
                    path_server.add_to_queue(["mobility_loop>path_server.destination_request", self.location])

                if topic == "path_server>mobility_loop.destination_response":
                    self.destination = msg
                    network.send("mobility_loop.lease_request", [self.location, self.destination])

                if topic == "mobility_loop.lease_response":
                    self.lease = msg
                    spatial_translation.add_to_queue(["mobility_loop>spatial_translation.set_destination", [self.location, self.destination]])

                if topic == "motion.destination_reached":
                    self.motion_complete = True
                    location_server.add_to_queue("mobility_loop>location_server.location_request", True)

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

mobility_loop = Mobility_Loop()
mobility_loop.daemon = True



class Message_Router(threading.Thread):
    """
        This class 
        
        incoming message topics:
            management.system_status_request
            management.system_reboot_request
            management.system_shutdown_request
            management.git_pull_request
            management.scripts_update_request
            mobility_loop.lease_response
            mobility_loop.enable_request
            path_server.paths_response
            path_server.path_to_available_paint_response
            location_server.location_from_lps_response
        outgoing message topics:
    
        synchronous functions:
         
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.management = management_init()
    def add_to_queue(self, msg):
        self.queue.put(msg)

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                print "message_router.main", topic, msg
                if topic == "management.system_status_request":
                    network.send("management.system_status_response", self.management.get_system_status(msg))
                    continue
                if topic == "management.system_reboot_request":
                    network.send("management.system_reboot_response", self.management.system_reboot())
                    continue
                if topic == "management.system_shutdown_request":
                    network.send("management.system_shutdown_response", self.management.system_shutdown())
                    continue
                if topic == "management.git_pull_request":
                    network.send("management.git_pull_response", self.management.git_pull(msg))
                    continue
                if topic == "management.scripts_update_request":
                    network.send("management.scripts_update_response", self.management.scripts_update(msg))
                    continue
                if topic == "mobility_loop.lease_response":
                    mobility_loop.add_to_queue([topic, msg])
                    continue
                if topic == "mobility_loop.enable_request":
                    mobility_loop.add_to_queue(topic, msg)
                    continue
                if topic == "path_server.stroke_paths_response":
                    path_server.add_to_queue([topic, msg])
                    continue
                if topic == "path_server.path_to_available_paint_response":
                    path_server.add_to_queue(topic, msg)
                    continue
                if topic == "location_server.location_from_lps_response":
                    location_server.add_to_queue(topic, msg)
                    continue

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

message_router = Message_Router()
message_router.daemon = True


class State_Checker(threading.Thread):
    # mostly used for loading data from async server
    def __init__(self):
        threading.Thread.__init__(self)
        #self.queue = Queue.Queue()

    #def add_to_queue(self, msg):
    #    self.queue.put(msg)

    def run(self):
        while True:
            #check that there are stroke_paths
            path_request_triggered = path_server.request_paths_if_needed()
            #check that there is fresh location data
            #if path_request_triggered:
            #    path_server.add_to_queue(["mobility_loop>path_server.destination_request", self.location])
            time.sleep(2.0)

state_checker = State_Checker()
state_checker.daemon = True

class Network(object):
    def __init__(self, hostname):
        self.hostname = hostname
        self.thirtybirds = network_init(
            hostname=hostname,
            role="client",
            discovery_multicastGroup=settings.discovery_multicastGroup,
            discovery_multicastPort=settings.discovery_multicastPort,
            discovery_responsePort=settings.discovery_responsePort,
            pubsub_pubPort=settings.pubsub_pubPort,
            message_callback=self.network_message_handler,
            status_callback=self.network_status_handler
        )

    def network_message_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        topic, msg =  topic_msg # separating just to eval msg.  best to do it early.  it should be done in TB.
        if len(msg) > 0: 
            try:
                msg = eval(msg)
            except Exception:
                pass
        message_router.add_to_queue([topic, msg])

    def network_status_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        print "Main.network_status_handler", topic_msg

    def send(self, topic, message): # just for convenience
        self.thirtybirds.send(topic, message)

    def subscribe_to_topic(self, topic): # just for convenience
        self.thirtybirds.subscribe_to_topic(topic)

#network = None # placeholder in global scope

def init(hostname):
    global network
    network = Network(hostname)
    motor_control.start()
    spatial_translation.start()    
    path_server.start()
    location_server.start()
    mobility_loop.start()
    message_router.start()
    state_checker.start()
    network.subscribe_to_topic("management.system_status_request")
    network.subscribe_to_topic("management.system_reboot_request")
    network.subscribe_to_topic("management.system_shutdown_request")
    network.subscribe_to_topic("management.git_pull_request")
    network.subscribe_to_topic("management.scripts_update_request")
    network.subscribe_to_topic("mobility_loop.lease_response")
    network.subscribe_to_topic("mobility_loop.enable_request")
    network.subscribe_to_topic("path_server.stroke_paths_response")
    network.subscribe_to_topic("path_server.paths_to_available_paint_response")
    network.subscribe_to_topic("location_server.location_from_lps_response")
    network.send("present", True)
    


