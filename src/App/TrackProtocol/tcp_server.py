import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((socket.gethostname(),1111))
server.listen()

while True:
    clientsocket, address = server.accept()
    print(f"Connected to {address}")
    print(clientsocket.recv(1024).decode('utf-8'))
    clientsocket.send("Hello Client!".encode('utf-8'))
    print(clientsocket.recv(1024).decode('utf-8'))
    clientsocket.send("Bye!".encode('utf-8'))
    clientsocket.close()