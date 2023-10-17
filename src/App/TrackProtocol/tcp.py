import socket
import pickle
import os

HEADERSIZE = 10

def run_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((socket.gethostname(), 1111))
    server.listen()

    connected_clients = []

    while True:
        clientsocket, address = server.accept()
        print(f"Connected to {address}")

        client_name = f"FS_NODE{len(connected_clients) + 1}"
        connected_clients.append((client_name, address))


        full_msg = b''
        new_msg = True
        msglen = 0

        while True:
            msg = clientsocket.recv(16)
            if new_msg:
                msglen = int(msg[:HEADERSIZE])
                new_msg = False

            full_msg += msg

            if len(full_msg)-HEADERSIZE == msglen:
                print(pickle.loads(full_msg[HEADERSIZE:]))

                break

        clientsocket.close()

def run_client():
    ip_address, port, directory = input("Enter [ip address] [port] [directory]: \n").split()
    port = int(port)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((ip_address, port))

    files_list = os.listdir(directory)

    packet = pickle.dumps(files_list)
    packet = bytes(f"{len(packet):<{HEADERSIZE}}", 'utf-8') + packet

    client.send(packet)

if __name__ == "__main__":
    choice = input("Press 1 to run as server, Press 2 to run as client: ")

    if choice == "1":
        run_server()
    elif choice == "2":
        run_client()
    else:
        print("Invalid choice. Please choose 1 or 2.")
