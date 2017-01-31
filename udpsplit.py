#!/usr/bin/env python3

import socket

source_ip = '10.42.0.1'
source_port = 7700

dest_ip = '127.0.0.1'
dest_ports = [7700,7701]

sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_in.bind((source_ip,source_port))
sock_out_0 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_out_1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while True:
    data, addr = sock_in.recvfrom(1024)
    sock_out_0.sendto(data, (dest_ip,dest_ports[0]))
    sock_out_1.sendto(data, (dest_ip,dest_ports[1]))

