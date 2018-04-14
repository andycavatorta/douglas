
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
        self.speed = float(abs(speed))
        proportion_of_circle = float(abs(degrees)) / 360.0
        length_of_arc = proportion_of_circle * self.circumference_of_rotation
        pulses_of_arc = length_of_arc * self.steps_per_rotation
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
        print "Motor_Control.add_to_queue", msg
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

class Spatial_Translation(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.cartisian_position = {"x":0.0, "y":0.0, "orientation":0.0}
        self.cartesian_destination = {"x":0.0, "y":0.0, "orientation":0.0} # fake initial values

    def set_cartisian_position(self, x, y, orientation):
        self.cartisian_position = {"x":x, "y":y, "orientation":orientation}

    #def set_cartesian_position_to_destination(self): # call this when motor_control confirms motion is finished

    def convert_vectors_to_motor_commands(self, distance, angle, brush_position_up):
        return [        
            {"action":"roll", "value":distance, "speed":0.5},
            {"action":"rotate", "value":angle, "speed":0.5},
            {"action":"brush", "value":brush_position_up, "speed":0.5}
        ]
        

    def convert_cartesian_position_and_destination_to_tangents(self, destination):
        self.cartesian_destination = destination
        origin = dict(self.cartisian_position) # for convenience
        #print "spatial_translation.translate_cartesian_to_vectors", origin, destination
        distance = math.sqrt(((origin['x'] - destination["x"])**2) + ((origin['y'] - destination["y"])**2))
        # calculate absolute heading relative to Cartesian space, not relative to bot
        if origin['x'] == destination["x"] and origin['y'] == destination["y"]: # no movement
            target_angle_relative_to_Cartesian_space = origin["orientation"]
        elif origin['x'] < destination["x"] and origin['y'] == destination["y"]: # x-axis positive
            target_angle_relative_to_Cartesian_space = 0.0
        elif origin['x'] > destination["x"] and origin['y'] == destination["y"]: # x-axis negative
            target_angle_relative_to_Cartesian_space = 180.0
        elif origin['x'] == destination["x"] and origin['y'] < destination["y"]: # y-axis positive
            target_angle_relative_to_Cartesian_space = 90.0
        elif origin['x'] == destination["x"] and origin['y'] > destination["y"]: # y-axis negative
            target_angle_relative_to_Cartesian_space = -90.0
        elif origin['x'] < destination["x"] and origin['y'] < destination["y"]: # somewhere in quadrant 1
            target_angle_relative_to_Cartesian_space =  math.degrees(math.acos( abs(destination["x"]-origin['x']) / distance) )
        elif origin['x'] > destination["x"] and origin['y'] < destination["y"]: # somewhere in quadrant 2
            target_angle_relative_to_Cartesian_space =  90 + math.degrees(math.acos( abs(destination["x"]-origin['x']) / distance) )
        elif origin['x'] > destination["x"] and origin['y'] > destination["y"]: # somewhere in quadrant 3
            target_angle_relative_to_Cartesian_space =  180 + math.degrees(math.acos( abs(destination["x"]-origin['x']) / distance) )
        elif origin['x'] < destination["x"] and origin['y'] > destination["y"]: # somewhere in quadrant 4
            target_angle_relative_to_Cartesian_space =  270 + math.degrees(math.acos( abs(destination["x"]-origin['x']) / distance) )
        else : # we should never end up here
            print "Coordinates_To_Vectors.calculate_vectors_from_target_coordinates cannot assign quadrant", origin['x'], destination["x"], origin['y'], destination["y"]
            distance = 0.0
            target_angle_relative_to_Cartesian_space = origin["orientation"]
            target_angle_relative_to_bot = 0.0
        target_angle_relative_to_bot = target_angle_relative_to_Cartesian_space - origin['orientation']        
        self.cartisian_position = {"x":destination["x"], "y":destination["y"], "orientation":target_angle_relative_to_Cartesian_space}
        return (distance, target_angle_relative_to_bot)

class Timed_Events(threading.Thread):
    def __init__(self, hostname, paths):
        threading.Thread.__init__(self)
        self.paths = paths

    def run(self):
        while True:
            time.sleep(20)
            self.paths.add_to_queue(("timed_events.request_strokes_if_empty",False))
            self.paths.add_to_queue(("motor_control.request_next_command",False))

class Paths(threading.Thread):
    def __init__(self, hostname, network, spatial_translation, motor_control):
        threading.Thread.__init__(self)
        self.hostname = hostname
        self.queue = Queue.Queue()
        self.network = network
        self.spatial_translation = spatial_translation
        self.motor_control = motor_control
        self.stroke_paths = []

    # avoid threading here and simply store stroke_paths in a queue?
    def add_to_queue(self, msg):
        self.queue.put(msg)

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                if topic == "timed_events.request_strokes_if_empty":
                    if len(self.stroke_paths) == 0:
                        self.network.thirtybirds.send("path_server.next_stroke_request", self.hostname)
                if topic == "path_server.next_stroke_response_{}".format(self.hostname):
                    self.stroke_paths = msg
                if topic == "motor_control.request_next_command":
                    while len(self.stroke_paths) > 0:
                        stroke_path = self.stroke_paths.pop(0)
                        print "stroke_path", stroke_path
                        vectors = self.spatial_translation.convert_cartesian_position_and_destination_to_tangents(stroke_path)
                        print "vectors", vectors
                        motor_commands = self.spatial_translation.convert_vectors_to_motor_commands(vectors[0], vectors[1], stroke_path['brush_up'])
                        for motor_command in motor_commands:
                            print "motor_command", motor_command
                            self.motor_control.add_to_queue(motor_command)

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

        self.spatial_translation = Spatial_Translation()
        self.spatial_translation.daemon = True
        self.spatial_translation.start()

        self.motor_control = Motor_Control()
        self.motor_control.daemon = True
        self.motor_control.start()

        self.paths = Paths(hostname, self.network, self.spatial_translation, self.motor_control)
        self.paths.daemon = True
        self.paths.start()

        self.timed_events = Timed_Events(hostname, self.paths)
        self.timed_events.daemon = True
        self.timed_events.start()
        
        

    def network_message_handler(self, topic_msg):
        topic, msg =  topic_msg # separating just to eval msg.  best to do it early.  it should be done in TB.
        print topic, msg
        if len(msg) > 0:
            try:
                msg = eval(msg)
            except Exception:
                pass
        self.add_to_queue(topic, msg)

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
                if topic == "path_server.next_stroke_response_{}".format(self.hostname):
                    self.paths.add_to_queue((topic,msg))
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
