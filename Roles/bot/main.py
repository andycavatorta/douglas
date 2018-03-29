
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
        self.current_motion = ["stop","rotate_right","rotate_left","roll_forward","roll_backward"][0]

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
        #print "Motor_Control.rotate", degrees, speed
        self.speed = float(abs(speed))
        #print "float(abs(degrees))", float(abs(degrees))
        proportion_of_circle = float(abs(degrees)) / 360.0
        #print "proportion_of_circle", proportion_of_circle
        length_of_arc = proportion_of_circle * self.circumference_of_rotation
        #print "length_of_arc", length_of_arc
        pulses_of_arc = length_of_arc * self.steps_per_rotation
        #print "pulses_of_arc", pulses_of_arc
        left_steps, right_steps = (pulses_of_arc, -pulses_of_arc) if degrees > 0 else (-pulses_of_arc, pulses_of_arc)

        self.current_motion = "rotate_right" if degrees > 0 else "rotate_left"

        self.finished = {
            "left_wheel":False,
            "right_wheel":False,
            "brush_arm":True
        }
        self.pulse_odometer = {
            "left_wheel":0,
            "right_wheel":0,
            "brush_arm":0
        }

        stepper_pulses.set("left_wheel", "speed", speed)
        stepper_pulses.set("right_wheel", "speed", speed)
        stepper_pulses.set("brush_arm", "speed", speed)

        stepper_pulses.set("left_wheel", "steps", left_steps * 4)
        stepper_pulses.set("right_wheel", "steps", right_steps * 4)
        stepper_pulses.set("brush_arm", "steps", 0)

    def roll(self, distance, speed): # distance units are in mm
        #print "Motor_Control.roll", distance, speed
        number_of_wheel_rotations = abs(distance) / self.wheel_circumference
        number_of_pulses = number_of_wheel_rotations * self.steps_per_rotation

        self.current_motion = "roll_forward" if distance > 0 else "roll_backward"

        self.finished = {
            "left_wheel":False,
            "right_wheel":False,
            "brush_arm":True
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
        #print "Motor_Control.brush_arm", brush_position_up, speed
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
        self.current_motion = "stop"
        self.previous_motion = "" # used only for debug

        self.finished = {
            "left_wheel":True,
            "right_wheel":True,
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
            if self.previous_motion != self.current_motion:
                print " self.current_motion",  self.current_motion, motor_name, data
                self.previous_motion = self.current_motion
            if motor_name in ["left_wheel", "right_wheel"]:
                self.pulse_odometer[motor_name] = data # collect pulse odometer for each motor
                left_distance  = self.pulse_odometer["left_wheel"]  / float(self.steps_per_rotation) * self.wheel_circumference * ( 1 if settings.motor_control["stepper_motors"]["left_wheel"]["backwards_orientation"] else -1)
                right_distance = self.pulse_odometer["right_wheel"] / float(self.steps_per_rotation) * self.wheel_circumference * ( 1 if settings.motor_control["stepper_motors"]["right_wheel"]["backwards_orientation"] else -1)
                average_distance = (abs(left_distance) + abs(right_distance)) / 2.0
                if self.current_motion == "rotate_left": # rotate left
                    proportion_of_circle = average_distance / self.circumference_of_rotation
                    degrees = proportion_of_circle * 360.0
                    #print "motor_callback", motor_name, msg_type, data, degrees
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["rotate", degrees]])
                    return
                if self.current_motion == "rotate_right": # rotate right
                    proportion_of_circle = average_distance / self.circumference_of_rotation
                    degrees = proportion_of_circle * 360.0
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["rotate", -degrees]])
                    return
                if self.current_motion == "roll_forward": # roll forward
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["roll", average_distance]])
                    return
                if self.current_motion == "roll_backward": # roll backward
                    location_server.add_to_queue(["motor_control>location_server.relative_odometry", ["roll", -average_distance]])
                    return

        if msg_type == "finished":
            #print "motor_callback", motor_name, msg_type, data
            self.finished[motor_name] = data
            if self.finished["left_wheel"] and self.finished["right_wheel"] and self.finished["brush_arm"]:
                self.add_to_queue(["finished", None, None])

    def add_to_queue(self, msg):
        #print "Motor_Control.add_to_queue", msg
        self.message_queue.put(msg)

    def run(self):
        while True:
            # if all motors are finished, 
            if self.finished["left_wheel"] and self.finished["right_wheel"] and self.finished["brush_arm"]:
                try:
                    command, value, speed = self.command_queue.get(False) # check the command queue
                    if command  == "rotate":
                        self.rotate(value, speed)
                    if command  == "roll":
                        self.roll(value, speed)
                    if command  == "brush":
                        self.brush_arm(value, speed)
                except Queue.Empty:
                    pass
            try:
                # block on waiting for all motors to acknowledge completion or disable
                command, value, speed = self.message_queue.get(False)
                if command in ["rotate","roll","brush"]:
                    self.command_queue.put([command, value, speed])
                if command == "enable":
                    stepper_pulses.set("left_wheel", "enable", value)
                    stepper_pulses.set("right_wheel", "enable", value)
                    stepper_pulses.set("brush_arm", "enable", value)
                if command == "finished":
                    mobility_loop.add_to_queue(["motion.destination_reached", True])
            except Queue.Empty:
                pass
            time.sleep(0.1)
            #except Exception as e:
            #    exc_type, exc_value, exc_traceback = sys.exc_info()
            #    print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

motor_control = Motor_Control()
motor_control.daemon = True


class Paths(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.stroke_paths = []
        #self.stroke_paths_cursor = 0

    def add_to_queue(self, msg):
        self.queue.put(msg)

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                if topic == "path_server.stroke_paths_response":
                    self.stroke_paths = msg
                    #self.stroke_paths_cursor = 0
                    for stroke_path in self.stroke_paths:
                        print stroke_path
                        time.sleep(10.0)

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

paths = Paths()
paths.daemon = True


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
        print topic, msg
        if topic == "path_server.stroke_paths_response_{}".format(self.hostname):
            paths.add_to_queue(["path_server.stroke_paths_response", msg])

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
    paths.start()
    #motor_control.start()
    #spatial_translation.start()    
    #path_server.start()
    #location_server.start()
    motor_control.start()
    spatial_translation.start()    
    #mobility_loop.start()
    #message_router.start()
    #state_checker.start()
    network.subscribe_to_topic("management.system_status_request")
    network.subscribe_to_topic("management.system_reboot_request")
    network.subscribe_to_topic("management.system_shutdown_request")
    network.subscribe_to_topic("management.git_pull_request")
    network.subscribe_to_topic("management.scripts_update_request")
    network.subscribe_to_topic("mobility_loop.lease_response")
    network.subscribe_to_topic("mobility_loop.enable_request")
    #network.subscribe_to_topic("path_server.stroke_paths_response")
    network.subscribe_to_topic("path_server.stroke_paths_response_{}".format(hostname))
    network.subscribe_to_topic("path_server.paths_to_available_paint_response")
    network.subscribe_to_topic("location_server.location_from_lps_response")
    network.send("present", True)
    


