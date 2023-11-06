import socket
import os
import threading

HEADERSIZE = 15

def handle_client(clientsocket, address, file_locator, file_sizes, available_files):
    global available_files_lock

    full_msg = b''

    # Read exactly 1 byte for the message_type
    message_type_bytes = clientsocket.recv(1)

    # Decode the message_type
    message_type = int.from_bytes(message_type_bytes, byteorder='big')

    if message_type == 1:

        # Adicionar tamanho dos ficheiros
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

        files_data = full_msg.decode("utf-8").split('|')
        print("here")
        # Adicionar arquivos e tamanhos ao dicionário file_sizes
        for file_data in files_data:
            file, size = file_data.split(',')
            file_sizes[file] = int(size)

        # Adicionar arquivos ao dicionário file_locator
        for file in file_sizes:
            if file not in file_locator:
                file_locator[file] = set([address[0]])
            else:
                file_locator[file].add(address[0])

        # Atualizar a lista de arquivos disponíveis
        available_files_lock.acquire()
        available_files.clear()
        available_files.extend(file_sizes.keys())
        available_files_lock.release()

        print(f"File sizes: {file_sizes}")
        print(f"File locator: {file_locator}")
        print(f"Available files: {available_files}")

    if message_type == 2:
        available_files_str = '|'.join(available_files)
        available_files_bytes = available_files_str.encode("utf-8")
        length = len(available_files_bytes)

        length_bytes = length.to_bytes(2, byteorder='big')

        packet = length_bytes + available_files_bytes

        clientsocket.sendall(packet)
    if message_type == 3:
        file_length = clientsocket.recv(2)
        file_length = int.from_bytes(file_length, byteorder='big')

        file_request = clientsocket.recv(file_length).decode("utf-8")

        if file_request in file_locator:
            file_location = ', '.join(file_locator[file_request])
            file_location_bytes = file_location.encode("utf-8")
            length = len(file_location_bytes)

            length_bytes = length.to_bytes(2, byteorder='big')

            packet = length_bytes + file_location_bytes

            clientsocket.sendall(packet)
        else:
            clientsocket.send("File not found".encode("utf-8"))

    clientsocket.close()

# Restante do código permanece o mesmo



def run_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((socket.gethostname(), 1111))
    server.listen()

    connected_clients = []
    file_locator = {}
    file_sizes = {}
    available_files = []

    while True:
        clientsocket, address = server.accept()
        print(f"Connected to {address}")

        connected_clients.append(address)

        client_handler = threading.Thread(target=handle_client, args=(clientsocket, address, file_locator, file_sizes, available_files))
        client_handler.start()


def run_client():
    ip_address, port, directory = input("Enter [ip address] [port] [directory]: ").split()
    port = int(port)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((ip_address, port))
    type_1(client, directory, port)
    client.close()

    while True:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip_address, port))

        os.system('clear')  # Clear the console

        print_menu()
        message_type = int(input("Enter message type: "))

        if message_type == 2:
            type_2(client)
        if message_type == 3:
            type_3(client)
        if message_type == 0:
            break

        if message_type != 0 and message_type != 2 and message_type != 3:
            print("\nInvalid Option....\n")


        input("Press Enter to continue...")


def split_file(file_path, chunk_size, output_directory):
    if os.path.isfile(file_path):
        file_name, file_extension = os.path.splitext(os.path.basename(file_path))
        parent_directory = os.path.dirname(os.path.dirname(output_directory))  # Alteração feita aqui
        file_parts_directory = os.path.join(parent_directory, f"{file_name}_parts")  # Caminho de saída modificado
        if not os.path.exists(file_parts_directory):
            os.makedirs(file_parts_directory)
            with open(file_path, 'rb') as file:
                index = 1
                while True:
                    data = file.read(chunk_size)
                    if not data:
                        break
                    part_file_name = f"{file_name}_part{index}{file_extension}"
                    with open(os.path.join(file_parts_directory, part_file_name), 'wb') as part_file:
                        part_file.write(data)
                    index += 1
        else:
            print(f"Directory {file_parts_directory} already exists. Skipping creation.")
    else:
        print(f"The provided path '{file_path}' does not point to a file.")




def type_1(client, directory, port):
    message_type = 1

    files_list = [file for file in os.listdir(directory) if not file.startswith('.')]
    files_list.sort()

    for file in files_list:
        file_directory = os.path.join(directory, f"{os.path.splitext(file)[0]}_parts")
        split_file(os.path.join(directory, file), 10, file_directory)

    length = len(files_list)

    message_type_bytes = message_type.to_bytes(1, byteorder='big')
    length_bytes = length.to_bytes(2, byteorder='big')
    port_bytes = port.to_bytes(2, byteorder='big')

    files_data = [f"{file},{os.path.getsize(os.path.join(directory, file))}" for file in files_list]
    files_list_str = '|'.join(files_data)
    files_list_bytes = files_list_str.encode("utf-8")

    packet = message_type_bytes + length_bytes + port_bytes + files_list_bytes

    client.send(packet)


def type_2(client):
    message_type = 2
    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes

    client.send(packet)

    # Receive the list of available files from the server
    length_bytes = client.recv(2)
    length = int.from_bytes(length_bytes, byteorder='big')

    available_files_lock.acquire()
    available_files_bytes = client.recv(length)
    available_files_str = available_files_bytes.decode("utf-8")
    available_files = available_files_str.split('|')
    available_files_lock.release()

    print("\n----------------------------------------------------------------")
    print(f"Available files: {available_files}")
    print("------------------------------------------------------------------\n")

def type_3(client):
    message_type = 3

    file_request = input("Enter the file you want to get information about: ")
    file_lenght = len(file_request)
    file_lenght_bytes = file_lenght.to_bytes(2, byteorder='big')
    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes + file_lenght_bytes + file_request.encode("utf-8")
    client.send(packet)

    # Receber a resposta do servidor
    response = client.recv(1024).decode("utf-8")
    print(f"Server's response: {response}")


def print_menu():
    print("---------------------------------------------------------------------------")
    print("WELCOME! CHOOSE ONE OF OUR MENU OPTIONS:")
    print("---------------------------------------------------------------------------")
    print("2 : View all files that are available")
    print("3 : Get information about a file of your choice")
    print("0 : Exit")
    print("---------------------------------------------------------------------------")



if __name__ == "__main__":
    try:
        choice = input("Press 1 to run as server, Press 2 to run as client: ")
        available_files_lock = threading.Lock()
        if choice == "1":
            run_server()
        elif choice == "2":
            run_client()
        else:
            print("Invalid choice. Please choose 1 or 2.")
    except KeyboardInterrupt:
        if os.name == 'posix':  # Verifica se o sistema operacional é baseado em Unix (Linux ou macOS)
            os.system('clear')
        elif os.name == 'nt':  # Verifica se o sistema operacional é o Windows
            os.system('cls')
        print("Program interrupted. Terminal cleared.")