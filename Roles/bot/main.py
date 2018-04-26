# next moves:
# define Motor instances in Motor_Control
# set up Motor Class



# receive pushed destination
# convert cartesian to vectors
# convert vectors to motor commands
# execute motor commands                        
#   capture pulse events with callback
#   convert pulses to vectors
#   convert vectors to cartesian position
#   send position info to server [?]
#
# listen for pause/resume messages from server
# listen for system management requests




#CONTROLLER
#    broadcasts lps data to each bot
# TO DO: FIDUCIAL MARKER OFFSET TO LPS DATA.  MAYBE DO THIS UPSTREAM ON SERVER?
# TO DO: HANDLE LEASES BEFORE SENDING PATHS




import commands
import math
import numpy as np
import os
import Queue
import RPi.GPIO as GPIO
import settings
import time
import threading
import traceback
import sys

from thirtybirds_2_0.Network.manager import init as network_init
from thirtybirds_2_0.Updates.manager import init as updates_init
from thirtybirds_2_0.PiUtils.management import init as management_init






class Motor(threading.Thread):
    def __init__(
            self, 
            name,
            pulse_pin, 
            dir_pin, 
            base_pulse_period = 0.001, 
            status_callback = False, 
            backwards_orientation = False
        ):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.name = name
        self.pulse_pin = pulse_pin
        self.dir_pin = dir_pin
        self.base_pulse_period = base_pulse_period
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pulse_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        GPIO.output(self.pulse_pin, GPIO.LOW)
        GPIO.output(self.dir_pin, GPIO.LOW)
        self.backwards_orientation = backwards_orientation
        self.status_callback = status_callback
        self.steps = 0
        self.steps_cursor = 0
        self.direction = True
        self.speed = 0.0
        self.enable = True
 

    def set_speed(self, speed): # valid values for speed are 0.0-1.0
        if 0.0 <= speed <= 1.0:
            self.speed = speed
        else:
            print "stepper_pulses.Motor speed out of range", speed

    def set_steps(self, steps): # valid value for steps is any integer
        self.steps = abs(int(steps))
        if self.steps > 0:
            self.direction = True if steps > 0 else False
            self.steps_cursor = 0
            if self.backwards_orientation:
                GPIO.output(self.dir_pin, GPIO.LOW if self.direction else GPIO.HIGH)
            else:
                GPIO.output(self.dir_pin, GPIO.HIGH if self.direction else GPIO.LOW)
        else:
            self.status_callback(self.name, "finished", True)

    def set_enable(self, enable): # enable:[True|False]
        self.enable = enable

    def add_to_queue(self, action, data): #actions: ["set_speed"|"set_steps"|"set_enable"]
        self.queue.put((action, data))

    def run(self):
        while True:
            try:
                action, data = self.queue.get(False)
                if action == "set_speed":
                    self.set_speed(data)
                if action == "set_steps":
                    self.set_steps(data)
                    self.status_callback(self.name, "started", None)
                if action == "set_enable":
                    self.set_enable(data)
            except Queue.Empty:
                pass
            if self.enable and self.speed > 0.0 and self.steps > self.steps_cursor:
                #print self.steps , self.steps_cursor
                GPIO.output(self.pulse_pin, GPIO.LOW)
                time.sleep(self.base_pulse_period * (1.0 / self.speed)) # actual sleep period will be longer b/c of processor scheduling
                GPIO.output(self.pulse_pin, GPIO.HIGH)
                time.sleep(self.base_pulse_period * (1.0 / self.speed)) # actual sleep period will be longer b/c of processor scheduling
                self.steps_cursor += 1 
                #if self.steps_cursor%10 == 0:
                self.status_callback(self.name, "update", self.steps_cursor)
                if self.steps == self.steps_cursor:
                    self.status_callback(self.name, "finished", self.steps_cursor)
            else:
                time.sleep(self.base_pulse_period)


class Motor_Control(threading.Thread):
    def __init__(self, default_motor_speed):
        threading.Thread.__init__(self)
        self.run_loop_queue = Queue.Queue()
        self.command_queue = Queue.Queue()
        self.brush_block = Queue.Queue()
        self.rotate_block = Queue.Queue()
        self.roll_block = Queue.Queue()
        self.default_motor_speed = default_motor_speed
        self.external_callback = lambda *args : args # blank for now
        self.brush = True
        self.distance_between_wheels = settings.motor_control["distance_between_wheels"] 
        self.steps_per_rotation = settings.motor_control["steps_per_rotation"] 
        self.wheel_circumference = settings.motor_control["wheel_circumference"] 
        self.circumference_of_rotation = self.distance_between_wheels * math.pi
        self.current_motor_command = ["finished", "brush", "rotate", "roll" ][0]
        self.pulse_odometer = {
            "left_wheel":0,
            "right_wheel":0,
            "brush":0
        }
        self.finished = {
            "left_wheel":True,
            "right_wheel":True,
            "brush":True
        }

        self.motors = {
            "left_wheel":Motor(
                "left_wheel",
                settings.motor_control["stepper_motors"]["left_wheel"]["pulse_pin"], 
                settings.motor_control["stepper_motors"]["left_wheel"]["dir_pin"], 
                settings.motor_control["stepper_motors"]["left_wheel"]["base_pulse_period"], 
                self.motor_event_callback, 
                settings.motor_control["stepper_motors"]["left_wheel"]["backwards_orientation"]
            ),
            "right_wheel":Motor(
                "right_wheel",
                settings.motor_control["stepper_motors"]["right_wheel"]["pulse_pin"], 
                settings.motor_control["stepper_motors"]["right_wheel"]["dir_pin"], 
                settings.motor_control["stepper_motors"]["right_wheel"]["base_pulse_period"], 
                self.motor_event_callback, 
                settings.motor_control["stepper_motors"]["right_wheel"]["backwards_orientation"]
            ),
            "brush":Motor(
                "brush",
                settings.motor_control["stepper_motors"]["brush"]["pulse_pin"], 
                settings.motor_control["stepper_motors"]["brush"]["dir_pin"], 
                settings.motor_control["stepper_motors"]["brush"]["base_pulse_period"], 
                self.motor_event_callback, 
                settings.motor_control["stepper_motors"]["brush"]["backwards_orientation"]
            ),
        }
        self.motors["left_wheel"].start()
        self.motors["right_wheel"].start()
        self.motors["brush"].start()

        self.motors["left_wheel"].add_to_queue("set_speed", 0.5)
        self.motors["right_wheel"].add_to_queue("set_speed", 0.5)
        self.motors["brush"].add_to_queue("set_speed", 0.5)


    def set_callback(self, callback):
        self.external_callback = callback # not thread safe but it will be okay

    def set_vectors(self, vectors, origin):
        self.add_to_queue(("set_vectors",(vectors, origin)))

    def motor_event_callback(self, motor_name, event_type, data):
        if event_type == "update":
            self.pulse_odometer[motor_name] = data 
            if self.current_motor_command == "roll":
                distance = self.pulse_odometer[motor_name] / float(self.steps_per_rotation) * self.wheel_circumference
                self.external_callback(motor_name, self.current_motor_command, distance)
            if self.current_motor_command == "rotate":
                length_of_arc = float(self.pulse_odometer[motor_name]) / (float(self.steps_per_rotation) ) 
                proportion_of_circle = length_of_arc / (self.circumference_of_rotation ) / 4.0
                target_angle_relative_to_bot = proportion_of_circle * 360.0
                self.external_callback(motor_name, self.current_motor_command, target_angle_relative_to_bot) 
        if event_type == "finished":
            self.finished[motor_name] = True 
            if self.finished["left_wheel"] and self.finished["right_wheel"] and self.finished["brush"]:
                if self.current_motor_command == "brush":
                    self.brush_block.put(True)
                    self.external_callback(motor_name, "finished_brush", self.pulse_odometer[motor_name]) # TO DO: ADD PARAMETERS
                if self.current_motor_command == "rotate":
                    length_of_arc = float(self.pulse_odometer[motor_name]) / (float(self.steps_per_rotation) ) 
                    proportion_of_circle = length_of_arc / (self.circumference_of_rotation ) / 4.0
                    target_angle_relative_to_bot = proportion_of_circle * 360.0
                    self.external_callback(motor_name, "finished_rotate", target_angle_relative_to_bot) # TO DO: ADD PARAMETERS
                    self.rotate_block.put(True)
                if self.current_motor_command == "roll":
                    distance = self.pulse_odometer[motor_name] / float(self.steps_per_rotation) * self.wheel_circumference
                    self.external_callback(motor_name, "finished_roll", distance) # TO DO: ADD PARAMETERS
                    self.roll_block.put(True)

    def add_to_queue(self, topic_data):
        self.run_loop_queue.put(topic_data)

    def run(self):
        while True:
            try:
                topic, data = self.run_loop_queue.get(True)
                if topic == "set_vectors":
                    vectors, origin = data
                    print "Motor_Control.run vectors, origin = ", vectors, origin
                    distance = vectors["distance"]
                    target_angle_relative_to_bot = vectors["target_angle_relative_to_bot"]
                    brush = vectors["brush"]
                    #distance, target_angle_relative_to_bot, brush = vectors
                    # convert vectors to three motor commands

                    ##### brush action #####
                    if self.brush != brush:
                        self.current_motor_command = "brush"
                        self.brush = brush
                        number_of_pulses = -300 if self.brush else 300
                        # something like
                        self.pulse_odometer = {
                            "left_wheel":0,
                            "right_wheel":0,
                            "brush":0
                        }
                        self.finished = {
                            "left_wheel":True,
                            "right_wheel":True,
                            "brush":False
                        }
                        self.motors["brush"].add_to_queue("set_steps", number_of_pulses)
                        # motors send pulse_odometer updates to callback
                        
                        self.brush_block.get(True)  # block until finished
                        # stepper_pulses sends updates to callback

                    ##### rotate action #####
                    if target_angle_relative_to_bot != 0.0:
                        self.current_motor_command = "rotate"
                        proportion_of_circle = float(abs(target_angle_relative_to_bot)) / 360.0
                        length_of_arc = proportion_of_circle * self.circumference_of_rotation
                        pulses_of_arc = length_of_arc * float(self.steps_per_rotation) * 4 # why * 4?
                        left_steps, right_steps = (pulses_of_arc, -pulses_of_arc) if target_angle_relative_to_bot > 0 else (-pulses_of_arc, pulses_of_arc)

                        # something like
                        self.pulse_odometer = {
                            "left_wheel":0,
                            "right_wheel":0,
                            "brush":0
                        }
                        self.finished = {
                            "left_wheel":False,
                            "right_wheel":False,
                            "brush":True
                        }
                        self.motors["left_wheel"].add_to_queue("set_steps", left_steps)
                        self.motors["right_wheel"].add_to_queue("set_steps", right_steps)
                        # motors send pulse_odometer updates to callback
                        
                        self.rotate_block.get(True)# block until both motors are finished
                        # stepper_pulses sends updates to callback

                    ##### roll action #####
                    if distance != 0.0:
                        self.current_motor_command = "roll"
                        number_of_wheel_rotations = abs(distance) / self.wheel_circumference
                        number_of_pulses = number_of_wheel_rotations * self.steps_per_rotation
                        left_steps, right_steps = (number_of_pulses, number_of_pulses) if distance > 0 else (-number_of_pulses, -number_of_pulses)
                        # something like
                        self.pulse_odometer = {
                            "left_wheel":0,
                            "right_wheel":0,
                            "brush":0
                        }
                        self.finished = {
                            "left_wheel":False,
                            "right_wheel":False,
                            "brush":True
                        }
                        self.motors["left_wheel"].add_to_queue("set_steps", left_steps)
                        self.motors["right_wheel"].add_to_queue("set_steps", right_steps)
                        # motors send pulse_odometer updates to callback
                        
                        self.roll_block.get(True) # block until finished
                        # stepper_pulses sends updates to callback




            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))




class Event_Loop(threading.Thread):
    def __init__(self, network, motor_control):
        threading.Thread.__init__(self)
        self.motor_control = motor_control
        self.network = network
        self.run_loop_queue = Queue.Queue()
        self.destination = {"x":0.0, "y":0.0, "brush":False, "orientation":0.0,"timestamp":0.0}
        self.location = {"x":0.0,"y":0.0,"orientation":0.0,"timestamp":0.0}
        self.origin = {"x":0.0,"y":0.0,"orientation":0.0,"timestamp":0.0}
        #self.location_odo = {"x":0.0,"y":0.0,"orientation":0.0,"timestamp":0.0} # this is used to accululate changes during transit

    def add_to_queue(self, topic_data):
        print "Event_Loop.add_to_queue topic_data=", topic_data
        self.run_loop_queue.put(topic_data)

    def convert_cartesian_to_polar(self, origin, destination):
        dx = destination["x"] - origin['x']
        dy = destination["y"] - origin['y']
        radius = np.sqrt(dx**2+dy**2)
        angle_relative_to_cartesian_space = math.degrees(np.arctan2(dy,dx))
        target_angle_relative_to_bot = angle_relative_to_cartesian_space - origin['orientation']
        return {
            "distance":radius, 
            "target_angle_relative_to_bot":target_angle_relative_to_bot, 
            "angle_relative_to_cartesian_space":angle_relative_to_cartesian_space
        }

    def convert_cartesian_origin_and_vector_to_cartesian_position(self, origin, distance, target_angle_relative_to_Cartesian_space):
        dx = distance * math.cos(math.radians(target_angle_relative_to_Cartesian_space))
        dy = distance * math.sin(math.radians(target_angle_relative_to_Cartesian_space))
        location = {"x": origin["x"]+dx ,"y": origin["y"] + dy  ,"orientation":target_angle_relative_to_Cartesian_space, "timestamp":time.time()}
        return location

    def motor_control_callback(self, motor_name, event_type, distance_or_angle): # this runs in the thread of motor_control # status, origin=None, vector=None
        #print "Event_Loop.motor_event_callback motor_name, event_type, pulse_odometer= ", motor_name, event_type, distance_or_angle
        if event_type == "rotate":
            angle = self.origin["orientation"] + distance_or_angle
            angle = angle-((int(angle)/360)*360.0)
            self.location["orientation"] = angle
            #self.origin = dict(self.location)
            #print self.location

        if event_type == "finished_rotate":
            #relative_location = self.convert_cartesian_origin_and_vector_to_cartesian_position(self.location, 0.0, distance_or_angle)
            angle = self.origin["orientation"] + distance_or_angle
            angle = angle-((int(angle)/360)*360.0)
            self.location["orientation"] = angle
            self.origin = dict(self.location)
            #print self.location

        if event_type == "roll":
            target_angle_relative_to_Cartesian_space = self.location["orientation"]
            relative_location = self.convert_cartesian_origin_and_vector_to_cartesian_position(self.origin, distance_or_angle, target_angle_relative_to_Cartesian_space)
            self.location["x"] = relative_location["x"]
            self.location["y"] = relative_location["y"]
            #print self.location

        if event_type == "finished_roll":
            target_angle_relative_to_Cartesian_space = self.location["orientation"]
            relative_location = self.convert_cartesian_origin_and_vector_to_cartesian_position(self.origin, distance_or_angle, target_angle_relative_to_Cartesian_space)
            self.location["x"] = relative_location["x"]
            self.location["y"] = relative_location["y"]

            self.origin = dict(self.location)
            print self.location
            #path_server.next_stroke_request

            self.network.thirtybirds.send("path_server.next_stroke_request", self.hostname)
        #if event_type == "finished":
        #return
        #if status == "in_transit":
        #    new_position = self.convert_cartesian_origin_and_vector_to_cartesian_position(self, origin, vector)
        #    self.network.thirtybirds.send("motor_control.location_update", new_position)
        #if status == "_finished":
        #    self.network.thirtybirds.send("motor_control.finished", False)

    def run(self):
        while True:
            try:
                topic, data = self.run_loop_queue.get(True)
                print "Event_Loop.run topic, data=", topic, data

                if topic[:25] == "event_loop.location_push_":
                    self.origin = dict(data)
                    self.location = dict(data)
                if topic == "event_loop.destination_push_":
                    self.destination = data
                    vectors = self.convert_cartesian_to_polar(self.origin, self.destination)
                    vectors["brush"] = data["brush"]
                    print "Event_Loop.run vectors=", vectors
                    self.motor_control.set_vectors(vectors, self.location)

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
    def __init__(self, hostname, default_motor_speed = 0.3):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.hostname = hostname
        self.management = management_init()
        self.default_motor_speed = default_motor_speed
        self.network = Network(hostname, self.network_message_handler, self.network_status_handler)

        self.motor_control = Motor_Control(default_motor_speed)
        self.motor_control.daemon = True
        self.motor_control.start()

        self.event_loop = Event_Loop(self.network, self.motor_control)
        self.event_loop.daemon = True
        self.event_loop.start()

        self.motor_control.set_callback(self.event_loop.motor_control_callback)

        self.network.thirtybirds.subscribe_to_topic("management.system_status_request")
        self.network.thirtybirds.subscribe_to_topic("management.system_reboot_request")
        self.network.thirtybirds.subscribe_to_topic("management.system_shutdown_request")
        self.network.thirtybirds.subscribe_to_topic("management.git_pull_request")
        self.network.thirtybirds.subscribe_to_topic("management.scripts_update_request")
        self.network.thirtybirds.subscribe_to_topic("event_loop.destination_push_{}".format(self.hostname))
        self.network.thirtybirds.subscribe_to_topic("event_loop.location_push_{}".format(self.hostname))
        


    def network_message_handler(self, topic_data):
        # this method runs in the thread of the caller, not the tread of Main
        topic, data =  topic_data # separating just to eval data.  best to do it early.  it should be done in TB.
        print topic, data
        if len(data) > 0:
            try:
                data = eval(data)
            except Exception:
                pass
        self.add_to_queue(topic, data)

    def network_status_handler(self, topic_data):
        # this method runs in the thread of the caller, not the tread of Main
        print "Main.network_status_handler", topic_data
        if topic_data["status"] == "device_discovered":
            self.network.thirtybirds.send("register_with_server", self.hostname)
            

    def add_to_queue(self, topic, data):
        print "main.add_to_queue", topic, data
        self.queue.put((topic, data))

    def run(self):
        while True:
            try:
                topic, data = self.queue.get(True)
                print topic, data
                if topic[:28] == "event_loop.destination_push_":
                    self.event_loop.add_to_queue(("event_loop.destination_push_",data))
                    continue
                if topic[:25] == "event_loop.location_push_":
                    self.event_loop.add_to_queue(("event_loop.location_push_",data))
                    continue
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

                #if topic == "motion.leases.request":
                #    self.network.thirtybirds.send("voice_1", self.voices[0].update("pitch_key", data))

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))





def init(hostname):
    main = Main(hostname)
    main.daemon = True
    main.start()
    return main

