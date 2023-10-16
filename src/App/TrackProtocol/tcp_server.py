import socket
import sys

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


server.bind((socket.gethostname(), 1111))
server.listen()

connected_clients = []

while True:
    clientsocket, address = server.accept()
    print(f"Connected to {address}")

    client_name = f"FS_NODE{len(connected_clients) + 1}"  # Set the name based on the number of connected clients
    connected_clients.append((client_name, address))


    clientsocket.send(client_name.encode('utf-8'))

    clientsocket.close()
