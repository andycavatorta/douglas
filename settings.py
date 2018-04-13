import math

server_hostname = "douglas_controller"
discovery_multicastGroup = "224.3.29.71"
discovery_multicastPort = 10010
discovery_responsePort = 10011
pubsub_pubPort = 10012
pubsub_pubPort2 = 10014

bot_names = [
    "douglas01",
    "douglas02",
    "douglas03",
    "douglas04",
    "douglas05",
    "douglas06",
    "douglas07",
    "douglas08",
    "douglas09",
    "douglas10",
    "douglas11",
    "douglas12",
    "douglas13",
    "douglas14",
    "douglas15",
    "douglas16",
    "douglas17",
    "douglas18",
    "douglas19",
    "douglas20",
]

server_names = [
    "douglas_controller", 
    "avl-visual", 
    "Ss-MacBook-Pro.local",
]

dashboard_names = [
    "douglas_dashboard"
]

location_server = {
    "location_disparity_threshold":{
        "x":0.1,
        "y":0.1,
        "orientation":5.0,
        "timestamp":5.0
    },
}

path_server = {
}




motor_control = {
    "stepper_motors":{
        "left_wheel":{
            "pulse_pin":26,
            "dir_pin":20,
            "base_pulse_period":0.0005,
            "status_callback":None,
            "backwards_orientation":False,
        },
        "right_wheel":{
            "pulse_pin":19,
            "dir_pin":16,
            "base_pulse_period":0.0005,
            "status_callback":None,
            "backwards_orientation":True,
        },
        "brush_arm":{
            "pulse_pin":6,
            "dir_pin":12,
            "base_pulse_period":0.0005,
            "status_callback":None,
            "backwards_orientation":True,
        }
    },
    "wheel_circumference":0.076 * math.pi,
    "distance_between_wheels":0.195,
    "steps_per_rotation":1600,
    "brush_arm_distance":200,
}   


paint_odometer_max_value =2.0, # meters

lps = {
    "host":"douglas-lps.local",
    "port":50683
}
