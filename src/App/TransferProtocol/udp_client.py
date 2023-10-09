import socket

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.sendto("Hello Server!".encode('utf-8'),(socket.gethostname(),1111))
print(client.recvfrom(1024)[0].decode('utf-8'))