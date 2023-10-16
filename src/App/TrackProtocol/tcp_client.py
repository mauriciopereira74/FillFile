import socket
import os

folder_path= '../../../cache'

try:
    os.mkdir(folder_path)
except FileExistsError:
    pass

result = os.listdir(folder_path)


client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((socket.gethostname(),1111))

name = client.recv(1024).decode('utf-8')
print(name)
