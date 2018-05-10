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
        self.canvas_size = canvas_size
        self.ingest_paths(drawing_name)

    def ingest_paths(self, drawing_name):
        try:
            with open('Paths/{}.json'.format(drawing_name)) as json_data:
                paths_in_td_format = json.load(json_data)
        except Exception as E:
            print "error opening {}".format(drawing_name)
            print E
            sys.exit()
        scaling_factor = self.canvas_size / 1200.0

        self.paths_in_bot_format = [] # one entry for each path defined
        for strokes in paths_in_td_format: # a path is a collection of strokes for one bot
            #print "strokes=",strokes
            coords_in_bot_format = []
            for stroke in strokes: # a stroke is a list of coords
                #print "stroke=",stroke
                #coords_in_bot_format = []
                for i in range(len(stroke)):
                    if i % 2 == 1: # only every other stroke.  must be a pythonic way to do this.
                        coords_in_bot_format.append(
                            {
                                "x":((stroke[i-1] * scaling_factor) - (self.canvas_size / 2.0) * scaling_factor) ,
                                "y":((stroke[i] * scaling_factor) - (self.canvas_size / 2.0) * scaling_factor) ,
                                "brush": False if i == 1 else True,
                            }
                        )
            self.paths_in_bot_format.append(coords_in_bot_format)
            #self.paths_in_bot_format.append(strokes_in_bot_format)
        self.paths_cursor = [0] * len(self.paths_in_bot_format)
        self.botname_to_path_ordinal = [False] * len(self.paths_in_bot_format)

    # botnames will be assigned to ordinals in the order requested.
    def assign_botname_to_path_ordinal(self, botname):
        if botname in self.botname_to_path_ordinal:
            return
        for i in range(len(self.botname_to_path_ordinal)):
            if self.botname_to_path_ordinal[i] is False: 
                self.botname_to_path_ordinal[i] = botname
                return
        print "Paths.assign_botname_to_path_ordinal: all names assigned already"

    def get_next_coords_for_path(self, botname):
        #print "=======> get_next_coords_for_path botname=", botname
        try:
            bot_ordinal = self.botname_to_path_ordinal.index(botname)
            #print "=======> get_next_coords_for_path botname=", bot_ordinal
        except ValueError as e:
            return False
        try:
            if self.paths_cursor[bot_ordinal] >= len(self.paths_in_bot_format[bot_ordinal]):
                print "resetting paths cursor for ", botname
                self.paths_cursor[bot_ordinal] = 0    
            path = self.paths_in_bot_format[bot_ordinal]
            #print "path",path
            path_cursor = self.paths_cursor[bot_ordinal]
            coords = path[path_cursor]
            #print "botname ",botname, "bot_ordinal ",bot_ordinal," path_cursor ",path_cursor," coords ",coords
            self.paths_cursor[bot_ordinal] += 1
            return coords
        except IndexError as e:
            return False

    def add_to_queue(self, topic_data):
        #print "Paths.add_to_queue", topic_data
        self.queue.put(topic_data)

    def run(self):
        while True:
            try:
                topic, data = self.queue.get(True)
                if topic == "path_server.register_bot":
                    self.assign_botname_to_path_ordinal(data)

                if topic == "path_server.next_stroke_request":
                    bot_hostname = data
                    send_topic = "{}_event_loop.destination_push".format(bot_hostname)
                    #send_topic = "path_server.next_stroke_response_{}".format(bot_hostname)
                    send_coords = self.get_next_coords_for_path(bot_hostname)
                    if send_coords is not False:
                        self.network.thirtybirds.send(send_topic,send_coords)
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
        self.connected_botnames = []
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
        self.network.thirtybirds.subscribe_to_topic("register_with_server")
        self.network.thirtybirds.subscribe_to_topic("warning.wifi_strength")
        print "Main started"

    def serve(self):
        self.add_to_queue("start_serving_coords",True)


    def network_message_handler(self, topic_data):
        # this method runs in the thread of the caller, not the tread of Main
        topic, data =  topic_data # separating just to eval msg.  best to do it early.  it should be done in TB.
        #print topic, data
        if len(data) > 0:
            try:
                data = eval(data)
            except Exception:
                pass
        self.add_to_queue(topic, data)

    def network_status_handler(self, topic_data):
        # this method runs in the thread of the caller, not the tread of Main
        print "Main.network_status_handler", topic_data

    def add_to_queue(self, topic, data):
        #print "main.add_to_queue", topic, data
        self.queue.put((topic, data))

    def run(self):
        while True:
            try:
                topic, data = self.queue.get(True)
                #print "Main run:", topic, data
                if topic == "location_server.location_from_lps_response":
                    pass
                if topic == "mobility_loop.enable_request":
                    pass
                if topic == "path_server.next_stroke_request":
                    self.paths.add_to_queue(["path_server.next_stroke_request", data])
                    #coords = self.paths.get_next_coords_for_path(data)
                    #if coords is not False:
                    #    topic = "{}_event_loop.destination_push".format(botname)
                    #    self.network.thirtybirds.send(topic, coords)
                if topic == "path_server.paths_response":
                    pass
                if topic == "path_server.path_to_available_paint_response":
                    pass
                if topic == "management.system_status_response":
                    print "management.system_status_response = ", data
                if topic == "management.system_reboot_response":
                    print "management.system_reboot_response = ", data
                if topic == "management.system_shutdown_response":
                    print "management.system_shutdown_response = ", data
                if topic == "management.git_pull_response":
                    print "management.git_pull_response = ", data
                if topic == "management.scripts_update_response":
                    print "management.scripts_update_response = ", data
                if topic == "start_serving_coords":
                    for botname in self.connected_botnames:
                        coords = self.paths.get_next_coords_for_path(botname)
                        if coords is not False:
                            send_topic = "{}_event_loop.destination_push".format(botname)
                            print "Main.run start_serving_coords, send_topic=", send_topic
                            self.network.thirtybirds.send(send_topic, coords)
                if topic == "register_with_server":
                    self.paths.assign_botname_to_path_ordinal(data)
                    self.connected_botnames.append(data)
                if topic == "warning.wifi_strength":
                    hostname, wifi_strength = data
                    print "{} - wifi signal notification for {}:{}".format(time.strftime("%I:%M:%S")
,hostname, wifi_strength)
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





