import socket
import os

HEADERSIZE = 15


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

        # Read exactly 1 byte for the message_type
        message_type_bytes = clientsocket.recv(1)

        # Decode the message_type
        message_type = int.from_bytes(message_type_bytes, byteorder='big')

        if message_type == 1:
            #adiconar tamanho dos ficheiros
            length_temp = clientsocket.recv(2)
            list_length = int.from_bytes(length_temp, byteorder='big')

            port_temp = clientsocket.recv(2)
            port_udp = int.from_bytes(port_temp, byteorder='big')

            full_msg = b''
            while True:
                chunk = clientsocket.recv(16)
                if not chunk:
                    break
                full_msg += chunk

            files_list = full_msg.decode("utf-8").split('|')

            print(f"Received files list: {files_list}")

        if message_type == 2:
            pass

        clientsocket.close()


def run_client():
    # ip_address, port, directory = input("Enter [ip address] [port] [directory]: \n").split()
    # port = int(port)
    ip_address = "192.168.1.233"
    port = 1111
    directory = "../../../cache"

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((ip_address, port))

    files_list = os.listdir(directory)
    files_list.sort()

    message_type = 1


    if message_type == 1:
        length = len(files_list)

        message_type_bytes = message_type.to_bytes(1, byteorder='big')
        length_bytes = length.to_bytes(2, byteorder='big')
        port_bytes = port.to_bytes(2,byteorder='big')

        files_list_str = '|'.join(files_list)
        files_list_bytes = files_list_str.encode("utf-8")

        packet = message_type_bytes + length_bytes + port_bytes + files_list_bytes

        client.sendall(packet)

    if message_type == 2:
        message_type_bytes = message_type.to_bytes(1, byteorder='big')

        packet = message_type_bytes

        client.send(packet)


if __name__ == "__main__":
    choice = input("Press 1 to run as server, Press 2 to run as client: ")

    if choice == "1":
        run_server()
    elif choice == "2":
        run_client()
    else:
        print("Invalid choice. Please choose 1 or 2.")
