
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


class Paths():
    def __init__(self, network):
        self.network = network
        self.queue = Queue.Queue()
        self.stroke_paths_tests = {
            "octogon":[
                {"x":-0.16, "y":0.20, "brush":True  },
                {"x":-0.16, "y":0.40, "brush":False  },
                {"x":0.0, "y":0.60, "brush":True  },
                {"x":0.20, "y":0.60, "brush":False  },
                {"x":0.36, "y":0.40, "brush":True  },
                {"x":0.36, "y":0.20, "brush":False  },
                {"x":0.20, "y":0.0, "brush":True  },
                {"x":0.0, "y":0.0, "brush":False  },
            ],
            "square":[
                {"action":"brush", "value":True, "speed":1.0 },
                {"action":"roll", "value":0.25, "speed":1.0 },
                {"action":"rotate", "value":90, "speed":1.0 },

                {"action":"brush", "value":False, "speed":1.0 },
                {"action":"roll", "value":0.25, "speed":1.0 },
                {"action":"rotate", "value":90, "speed":1.0 },

                {"action":"brush", "value":True, "speed":1.0 },
                {"action":"roll", "value":0.25, "speed":1.0 },
                {"action":"rotate", "value":90, "speed":1.0 },

                {"action":"brush", "value":False, "speed":1.0 },
                {"action":"roll", "value":0.25, "speed":1.0 },
                {"action":"rotate", "value":90, "speed":1.0 },
            ]
        }
        self.stroke_paths = {
            "douglas00":self.stroke_paths_tests["square"],
            "douglas01":self.stroke_paths_tests["square"],
            "douglas02":self.stroke_paths_tests["square"],
            "douglas03":self.stroke_paths_tests["square"],
            "douglas04":self.stroke_paths_tests["square"],
            "douglas05":self.stroke_paths_tests["square"],
            "douglas06":self.stroke_paths_tests["square"],
            "douglas07":self.stroke_paths_tests["square"],
            "douglas08":self.stroke_paths_tests["square"],
            "douglas09":self.stroke_paths_tests["square"],
        }
    def send_stroke_paths(self, bot_id=False):
            if bot_id:
                self.network.thirtybirds.send("path_server.stroke_paths_response_{}".format(bot_id),self.stroke_paths[bot_id])
            else:
                for bot_id in self.stroke_paths:
                    self.network.thirtybirds.send("path_server.stroke_paths_response_{}".format(bot_id),self.stroke_paths[bot_id])


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
    def __init__(self, hostname):
        threading.Thread.__init__(self)
        self.network = Network(hostname, self.network_message_handler, self.network_status_handler)
        self.queue = Queue.Queue()

        self.paths = Paths(self.network)
        #self.paths.daemon = True
        #self.paths.start()

        #self.leases = Leases(self.network)
        #self.leases.daemon = True
        #self.leases.start()

        #self.location = Location()
        #self.location.daemon = True
        #self.location.start()

        self.network.thirtybirds.subscribe_to_topic("location_server.location_from_lps_response")
        self.network.thirtybirds.subscribe_to_topic("mobility_loop.lease_request")
        self.network.thirtybirds.subscribe_to_topic("mobility_loop.enable_request")
        self.network.thirtybirds.subscribe_to_topic("path_server.stroke_paths_request")
        self.network.thirtybirds.subscribe_to_topic("path_server.paths_response")
        self.network.thirtybirds.subscribe_to_topic("path_server.path_to_available_paint_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_status_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_reboot_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_shutdown_response")
        self.network.thirtybirds.subscribe_to_topic("management.git_pull_response")
        self.network.thirtybirds.subscribe_to_topic("management.scripts_update_response")
        self.network.thirtybirds.subscribe_to_topic("present")

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
                if topic == "path_server.stroke_paths_request":
                    self.paths.add_to_queue(["path_server.stroke_paths_request", False])
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

def init(hostname):
    global main
    main = Main(hostname)
    main.daemon = True
    main.start()
    return main





