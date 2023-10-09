import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((socket.gethostname(),1111))

client.send("Hello Server!".encode('utf-8'))
print(client.recv(1024).decode('utf-8'))
client.send("Bye!".encode('utf-8'))
print(client.recv(1024).decode('utf-8'))
