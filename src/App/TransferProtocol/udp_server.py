import socket

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((socket.gethostname(),1111))

message, address = server.recvfrom(1024)
print(mesxsage.decode('utf-8'))
server.sendto("Hello Client!".encode('utf-8'),address)