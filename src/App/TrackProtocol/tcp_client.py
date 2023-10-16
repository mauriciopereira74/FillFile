import pickle
import socket
import os
import sys

if len(sys.argv) < 3:
    print("Usage: python3 dnscl.py [ip address] [domain] [dir]")
    exit()

# parsing
ip_address = sys.argv[1]
domain = int(sys.argv[2])
dir = sys.argv[3]

folder_path= '../../../cache'

try:
    os.mkdir(folder_path)
except FileExistsError:
    pass

files_list = os.listdir(dir)

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((ip_address,domain))

name = client.recv(1024).decode('utf-8')

