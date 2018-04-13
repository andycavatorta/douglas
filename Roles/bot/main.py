
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
#from thirtybirds_2_0.Adaptors.Actuators import stepper_pulses


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
        
        if msg_type != "steps_cursor":
            print "motor_callback", motor_name, msg_type, data

        if msg_type == "finished":
            self.finished[motor_name] = True
            
    def add_to_queue(self, msg):
        #print "Motor_Control.add_to_queue", msg
        self.message_queue.put(msg)

    def run(self):
        while True:
            try:
                command = self.message_queue.get(True)
                print "-----> command", command
                if command["action"] in ["rotate", "roll", "brush"]:
                    self.finished = {
                        "left_wheel":False,
                        "right_wheel":False,
                        "brush_arm":False
                    }
                if command["action"] == "rotate":
                    self.rotate(command["value"], command["speed"])
                if command["action"] == "roll":
                    self.roll(command["value"], command["speed"])
                if command["action"] == "brush":
                    self.brush_arm(command["value"], command["speed"])
                while not self.finished["left_wheel"] or not self.finished["right_wheel"] or not self.finished["brush_arm"]:
                    time.sleep(0.1)

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

#motor_control = Motor_Control()
#motor_control.daemon = True


class Paths():
    def __init__(self, hostname, network):
        self.queue = Queue.Queue()
        self.network = network
        self.stroke_paths = []
        self.network.thirtybirds.send("path_server.next_stroke_request", hostname)


    # avoid threading here and simply store stroke_paths in a queue?
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
                        motor_control.add_to_queue(stroke_path)
                        #time.sleep(4.0)

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))


class Network(object):
    def __init__(self, hostname, network_message_handler, network_status_handler):
        self.hostname = hostname
        self.thirtybirds = network_init(
            hostname=self.hostname,
            role="client",
            discovery_multicastGroup=settings.discovery_multicastGroup,
            discovery_multicastPort=settings.discovery_multicastPort,
            discovery_responsePort=settings.discovery_responsePort,
            pubsub_pubPort=settings.pubsub_pubPort,
            message_callback=network_message_handler,
            status_callback=network_status_handler
        )


class Main(threading.Thread):
    def __init__(self, hostname):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.hostname = hostname
        self.network = Network(hostname, self.network_message_handler, self.network_status_handler)
        #self.network = network_init(
        #    hostname=self.hostname,
        #    role="client",
        #    discovery_multicastGroup=settings.discovery_multicastGroup,
        #    discovery_multicastPort=settings.discovery_multicastPort,
        #    discovery_responsePort=settings.discovery_responsePort,
        #    pubsub_pubPort=settings.pubsub_pubPort,
        #    message_callback=self.network_message_handler,
        #    status_callback=self.network_status_handler
        #)
        self.network.thirtybirds.subscribe_to_topic("management.system_status_request")
        self.network.thirtybirds.subscribe_to_topic("management.system_reboot_request")
        self.network.thirtybirds.subscribe_to_topic("management.system_shutdown_request")
        self.network.thirtybirds.subscribe_to_topic("management.git_pull_request")
        self.network.thirtybirds.subscribe_to_topic("management.scripts_update_request")
        self.network.thirtybirds.subscribe_to_topic("mobility_loop.lease_response")
        self.network.thirtybirds.subscribe_to_topic("mobility_loop.enable_request")
        self.network.thirtybirds.subscribe_to_topic("path_server.next_stroke_response_{}".format(hostname))
        self.network.thirtybirds.subscribe_to_topic("path_server.paths_to_available_paint_response")
        self.network.thirtybirds.subscribe_to_topic("location_server.location_from_lps_response")
        self.network.thirtybirds.send("present", True)
        self.paths = Paths(hostname, self.network)

    def network_message_handler(self, topic_msg):
        print "main.add_to_queue", topic, msg
        self.queue.put((topic, msg))

    def network_status_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        print "Main.network_status_handler", topic_msg

    def add_to_queue(self, topic, msg): # event messages may come from network or internally
        #print "main.add_to_queue", topic, msg
        self.queue.put((topic, msg))

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))






def init(hostname):
    main = Main(hostname)
    main.daemon = True
    main.start()
    return main

    #global network
    #network = Network(hostname)
    #paths.start()
    #motor_control.start()
    #spatial_translation.start()    
    #path_server.start()
    #location_server.start()
    #motor_control.start()
    #spatial_translation.start()
    #mobility_loop.start()
    #message_router.start()
