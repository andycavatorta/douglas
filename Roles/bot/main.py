
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
                        time.sleep(1.0)

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
    network.subscribe_to_topic( == "path_server.stroke_paths_response_{}".format(self.hostname)):

    network.subscribe_to_topic("path_server.paths_to_available_paint_response")
    network.subscribe_to_topic("location_server.location_from_lps_response")
    network.send("present", True)
    


