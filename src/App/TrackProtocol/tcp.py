import socket
import pickle
import os
import json

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

        # Lê exatamente 1 byte para a message_type
        message_type_bytes = clientsocket.recv(1)

        # Decodifica a mensagem_type
        message_type = int.from_bytes(message_type_bytes, byteorder='big')

        # type 1 : 2 bytes de length, 2 bytes de porta udp, length da lista

        if message_type == 1:

            length_temp = clientsocket.recv(2)
            list_length = int.from_bytes(length_temp, byteorder='big')

            port_temp = clientsocket.recv(2)
            port_udp = int.from_bytes(port_temp, byteorder='big')

            files_list = []
            for _ in range(list_length):
                file_bytes = clientsocket.recv(
                    HEADERSIZE)  # assumindo que os nomes dos arquivos são menores que HEADERSIZE
                files_list.append(str(file_bytes))

            print(f"Received files list: {files_list}")

            pass

        if message_type == 2:

            print("tipo 2")

            pass

        clientsocket.close()


def run_client():
    ip_address, port, directory = input("Enter [ip address] [port] [directory]: \n").split()
    port = int(port)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((ip_address, port))

    files_list = os.listdir(directory)

    message_type = 2

    if message_type == 1 :

        length = 100

        message_type_bytes = message_type.to_bytes(1, byteorder='big')
        lenght_bytes = length.to_bytes(2, byteorder='big')

        message = {"type": message_type, "lenght": length, "files": files_list}
        message = pickle.dumps(message)

        # Envia a mensagem_type seguida pela mensagem
        packet = message_type_bytes + lenght_bytes + bytes(f"{len(message):<{HEADERSIZE}}", 'utf-8') + message

        client.send(packet)
        pass

    if message_type == 2:

        message_type_bytes = message_type.to_bytes(1, byteorder='big')

        packet = message_type_bytes

        client.send(packet)


        pass
    


if __name__ == "__main__":
    choice = input("Press 1 to run as server, Press 2 to run as client: ")

    if choice == "1":
        run_server()
    elif choice == "2":
        run_client()
    else:
        print("Invalid choice. Please choose 1 or 2.")
