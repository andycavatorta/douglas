import commands


text_block_str = commands.getstatusoutput("cat /proc/meminfo")[1]
text_block_l = text_block_str.split("\n")
for line in text_block_l:
    if line.startswith("MemFree:"):
        line_l = line.split()
        kb = float(line_l[1])
        mb = kb/1000.0
        print mb

    #if line.startswith("/dev/sda2") or line.startswith("/dev/root"):
    #    disk_free = line.split()[3]




"""
import math
import numpy as np

def convert_cartesian_to_polar(origin, destination):
    dx = destination["x"] - origin['x']
    dy = destination["y"] - origin['y']
    radius = np.sqrt(dx**2+dy**2)
    angle_relative_to_cartesian_space = math.degrees(np.arctan2(dy,dx))
    target_angle_relative_to_bot = angle_relative_to_cartesian_space - origin['orientation']
    print origin['x'], origin['y'], destination["x"], destination["y"]
    print "dx=", dx
    print "dy=", dy
    print "radius=", radius
    print "angle_relative_to_cartesian_space=", angle_relative_to_cartesian_space
    print "target_angle_relative_to_bot=", target_angle_relative_to_bot
    print ""

convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":0.0, "y":0.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":1.0, "y":0.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":1.0, "y":1.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":0.0, "y":1.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":-1.0, "y":1.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":-1.0, "y":0.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":-1.0, "y":-1.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":0.0, "y":-1.0})
convert_cartesian_to_polar({"x":0.0, "y":1.0, "orientation": 0.0},{"x":1.0, "y":-1.0})
"""





