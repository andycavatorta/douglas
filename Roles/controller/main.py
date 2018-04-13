import json
import os
import Queue
#import RPi.GPIO as GPIO
import random
import settings
import time
import threading
import traceback
import socket
import sys


BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
THIRTYBIRDS_PATH = "%s/thirtybirds_2_0" % (UPPER_PATH )

from thirtybirds_2_0.Network.manager import init as network_init


class Paths(threading.Thread):
    def __init__(self, drawing_name, canvas_size, network):
        threading.Thread.__init__(self)
        self.network = network
        self.queue = Queue.Queue()
        self.drawing_name = drawing_name
        try:
            with open('Paths/{}.json'.format(drawing_name)) as json_data:
                touch_designer_path_data = json.load(json_data)
        except Exception as E:
            print "error opening {}".format(drawing_name)
            sys.exit()
        scaling_factor = canvas_size / 1200.0
        self.douglas_strokes = []
        for stroke in touch_designer_path_data:
            douglas_stroke = []
            for i in range(len(stroke)):
                if i % 2 == 1:
                    douglas_stroke.append(
                        {
                            "x":(stroke[i-1] * scaling_factor) - (canvas_size / 2.0),
                            "y":(stroke[i] * scaling_factor) - (canvas_size / 2.0) * scaling_factor,
                            "brush_up": True if i == 1 else False,
                        }
                    )
            self.douglas_strokes.append(douglas_stroke)

    def add_to_queue(self, msg):
        print "Paths.add_to_queue", msg
        self.queue.put(msg)

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                print "Paths.run", topic, msg
                if topic == "path_server.next_stroke_request":
                    bot_id = msg
                    self.network.thirtybirds.send("path_server.next_stroke_response_{}".format(bot_id),self.douglas_strokes.pop(0))
            except Exception as E:
                print E


class Network(object):
    def __init__(self, hostname, network_message_handler, network_status_handler):
        self.hostname = hostname
        self.thirtybirds = network_init(
            hostname=self.hostname,
            role="server",
            discovery_multicastGroup=settings.discovery_multicastGroup,
            discovery_multicastPort=settings.discovery_multicastPort,
            discovery_responsePort=settings.discovery_responsePort,
            pubsub_pubPort=settings.pubsub_pubPort,
            message_callback=network_message_handler,
            status_callback=network_status_handler
        )

# Main handles network send/recv and can see all other classes directly
class Main(threading.Thread):
    def __init__(self, hostname, drawing_name, canvas_size, lps_ip):
        threading.Thread.__init__(self)
        self.network = Network(hostname, self.network_message_handler, self.network_status_handler)
        self.queue = Queue.Queue()
        self.paths = Paths(drawing_name, canvas_size, self.network)
        self.paths.daemon = True
        self.paths.start()

        #self.leases = Leases(self.network)
        #self.leases.daemon = True
        #self.leases.start()

        #self.location = Location()
        #self.location.daemon = True
        #self.location.start()

        self.network.thirtybirds.subscribe_to_topic("location_server.location_from_lps_response")
        self.network.thirtybirds.subscribe_to_topic("mobility_loop.lease_request")
        self.network.thirtybirds.subscribe_to_topic("mobility_loop.enable_request")
        self.network.thirtybirds.subscribe_to_topic("path_server.next_stroke_request")
        self.network.thirtybirds.subscribe_to_topic("path_server.paths_response")
        self.network.thirtybirds.subscribe_to_topic("path_server.path_to_available_paint_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_status_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_reboot_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_shutdown_response")
        self.network.thirtybirds.subscribe_to_topic("management.git_pull_response")
        self.network.thirtybirds.subscribe_to_topic("management.scripts_update_response")
        self.network.thirtybirds.subscribe_to_topic("present")
        print "Main started"

    def network_message_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
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

    def add_to_queue(self, topic, msg):
        print "main.add_to_queue", topic, msg
        self.queue.put((topic, msg))

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                print topic, msg
                if topic == "location_server.location_from_lps_response":
                    pass
                if topic == "mobility_loop.lease_request":
                    self.leases.add_to_queue(["mobility_loop.lease_request", msg])
                    pass
                if topic == "mobility_loop.enable_request":
                    pass
                if topic == "path_server.next_stroke_request":
                    self.paths.add_to_queue(["path_server.next_stroke_request", msg])
                if topic == "path_server.paths_response":
                    pass
                if topic == "path_server.path_to_available_paint_response":
                    pass
                if topic == "management.system_status_response":
                    pass
                if topic == "management.system_reboot_response":
                    pass
                if topic == "management.system_shutdown_response":
                    pass
                if topic == "management.git_pull_response":
                    pass
                if topic == "management.scripts_update_response":
                    pass
                if topic == "present":
                    pass
                #if topic == "motion.leases.request":
                #    self.network.thirtybirds.send("voice_1", self.voices[0].update("pitch_key", msg))

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

#main = None # reference here for 

def init(hostname, drawing_name, canvas_size, lps_ip):
    main = Main(hostname, drawing_name, canvas_size, lps_ip)
    main.daemon = True
    main.start()
    return main





