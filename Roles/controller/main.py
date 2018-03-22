
import os
import Queue
#import RPi.GPIO as GPIO
import settings
import time
import threading
import traceback
import sys


BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
THIRTYBIRDS_PATH = "%s/thirtybirds_2_0" % (UPPER_PATH )

#sys.path.append(BASE_PATH)
#sys.path.append(UPPER_PATH)

from thirtybirds_2_0.Network.manager import init as network_init

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
        #self.pedals = Pedals(self.add_to_queue)
        #self.pedals.daemon = True
        #self.pedals.start()
        #self.network.thirtybirds.subscribe_to_topic("system")  # subscribe to all system messages
        self.network.thirtybirds.subscribe_to_topic("path_server.stroke_paths_request")
        self.network.thirtybirds.subscribe_to_topic("mobility_loop.lease_request")
        self.network.thirtybirds.subscribe_to_topic("management.system_status_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_reboot_response")
        self.network.thirtybirds.subscribe_to_topic("management.system_shutdown_response")
        self.network.thirtybirds.subscribe_to_topic("management.git_pull_response")
        self.network.thirtybirds.subscribe_to_topic("management.scripts_update_response")
        self.network.thirtybirds.subscribe_to_topic("present")

    def network_message_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        topic, msg =  topic_msg # separating just to eval msg.  best to do it early.  it should be done in TB.
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
        self.queue.put((topic, msg))

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                print topic, msg

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





