import socket
import sys

# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect the socket to the port where the server is listening
server_address = ('192.168.0.20', 50000)
print >>sys.stderr, 'connecting to %s port %s' % server_address
sock.connect(server_address)

location_json_accumulator = ""
while True:
        data = sock.recv(1)
        location_json_accumulator += data
        if data == "]":
            print location_json_accumulator
            location_json_accumulator = ""
