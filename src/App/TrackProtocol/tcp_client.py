import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((socket.gethostname(),1111))

name = client.recv(1024).decode('utf-8')
print(name)
