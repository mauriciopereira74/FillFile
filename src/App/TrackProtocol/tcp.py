import socket
import os
import sys
import threading
import json
import queue
import random
import time
from tkinter import Tk, Label, Button, Frame, Text, Scrollbar, Entry, END
from time import sleep

PARTSIZE = 64000
global download_lock
global lock
HEADERSIZE = 64100
global condition
queue_recv = queue.Queue()
download_dict = {}


def handle_client(clientsocket, address, files_info, files_parts_info, available_files, files_lock):
    while True:

        # Read exactly 1 byte for the message_type
        message_type_bytes = clientsocket.recv(1)

        # Decode the message_type
        message_type = int.from_bytes(message_type_bytes, byteorder='big')

        if message_type == 0:

            print(f"Connection from {address} terminated.")

            # Remove client's IP from files_info and files_parts_info
            with files_lock:
                for file, info in list(files_info.items()):
                    _, _, ips, _ = info
                    ips_list = list(ips)
                    if address[0] in ips_list:
                        ips_list.remove(address[0])
                        # If the client was the only one associated with the file, remove the file from available_files
                        if len(ips_list) == 0:
                            available_files.discard(file)
                            # Remove the file from files_info
                            del files_info[file]

                for part, info in list(files_parts_info.items()):
                    _, ips, _ = info
                    ips_list = list(ips)
                    if address[0] in ips_list:
                        ips_list.remove(address[0])
                        files_parts_info[part] = (info[0], tuple(ips_list), info[2])

                        # If no clients are associated with the part, remove it from files_parts_info
                        if len(ips_list) == 0:
                            del files_parts_info[part]
            clientsocket.close()
            break


        elif message_type == 1:
            # Receive length information
            length_temp = clientsocket.recv(3)
            list_length = int.from_bytes(length_temp, byteorder='big')

            port_temp = clientsocket.recv(2)
            port_udp = int.from_bytes(port_temp, byteorder='big')

            # Receive the complete message
            msg = clientsocket.recv(list_length)
            # Decode the message and split into files and file parts using the '|' delimiter
            files_data = msg.decode("utf-8").split('|')
            files_data = list(filter(None, files_data))

            

            # Adicionar arquivos e informações ao dicionário files_info
            # Inicialize uma lista vazia para armazenar os IPs
            ips_list = []
            file_parts_aux = []
            with files_lock:

                # Adicionar arquivos e informações ao dicionário files_info
                for file in files_data:
                    file, size = file.split(',')
                    file_name, dot = file.split('.')
                    #num_parts = sum(1 for part in files_parts_data if part.startswith(file_name))
                    ip = address[0]

                    num_parts_aux = int(size) // PARTSIZE
                    last_part_size = int(size) % PARTSIZE

                    # Criar entradas para as partes na lista files_parts_data
                    file_parts_aux.extend([
                        f"{file_name}_part{i + 1}.{dot},{PARTSIZE}" for i in range(num_parts_aux)
                    ])

                    if num_parts_aux == 0 or last_part_size > 0:
                        file_parts_aux.append(f"{file_name}_part{num_parts_aux + 1}.{dot},{last_part_size}")

                    # Verifique se o arquivo já está no dicionário
                    if file in files_info:
                        # Se estiver, obtenha a lista de IPs existente e adicione o novo IP
                        _, _, _, port_udp = files_info[file]
                        ips_list = list(files_info[file][-2])  # Converta a tupla para uma lista
                        if ip not in ips_list:
                            ips_list.append(ip)
                        # Atualize o dicionário com a nova lista de IPs
                        files_info[file] = (int(size), num_parts_aux + 1, tuple(ips_list),
                                            port_udp)  # Converta a lista de IPs de volta para uma tupla
                    else:
                        # Se o arquivo não estiver no dicionário, crie uma nova entrada com a lista de IPs
                        files_info[file] = (int(size), num_parts_aux + 1, [ip], port_udp)


                # Inicialize uma lista vazia para armazenar os IPs
                ips_list_parts = []

                # Adicionar partes e informações ao dicionário files_parts_info
                for item in file_parts_aux:
                    part, size = item.split(',')
                    file_name, part_num = part.split('_part')
                    ip = address[0]

                    # Form the part key
                    part_key = f"{file_name}_part{part_num}"

                    # Verifique se a parte já está no dicionário
                    if part_key in files_parts_info:
                        # Se estiver, obtenha a lista de IPs existente e adicione o novo IP
                        _, existing_ip, _ = files_parts_info[part_key]
                        ips_list_parts = list(existing_ip)  # Converta a tupla para uma lista
                        if ip not in ips_list_parts:
                            ips_list_parts.append(ip)
                        # Atualize o dicionário com a nova lista de IPs
                        files_parts_info[part_key] = (int(size), tuple(ips_list_parts), port_udp)
                    else:
                        # Se a parte não estiver no dicionário, crie uma nova entrada com a lista de IPs
                        files_parts_info[part_key] = (int(size), [ip], port_udp)

                    # Adicionar nomes de arquivos ao conjunto available_files
                    for file in files_data:
                        file_name, _ = file.split(',')
                        available_files.add(file_name)

                #print(f"Available files: {available_files}")
                #print(f"Files Info: {files_info}")
                #print(f"Files Parts Info: {files_parts_info}")


        elif message_type == 2:

            available_files_str = '|'.join(available_files)
            available_files_bytes = available_files_str.encode("utf-8")
            length = len(available_files_bytes)

            length_bytes = length.to_bytes(2, byteorder='big')

            packet = length_bytes + available_files_bytes

            clientsocket.sendall(packet)


        elif message_type == 3:

            file_length = clientsocket.recv(2)
            file_length = int.from_bytes(file_length, byteorder='big')

            file_request = clientsocket.recv(file_length).decode("utf-8")

            response_data = json.dumps(files_info)

            # Obtendo o tamanho da resposta
            response_length = len(response_data)
            response_length_bytes = response_length.to_bytes(2, byteorder='big')

            packet = response_length_bytes + response_data.encode("utf-8")

            # Enviando o tamanho da resposta e a resposta ao cliente em um só pacote
            clientsocket.send(packet)

        elif message_type == 4:

            file_length = clientsocket.recv(2)
            file_length = int.from_bytes(file_length, byteorder='big')

            file_request = clientsocket.recv(file_length).decode("utf-8")

            file_request, _ = file_request.split(".")

            # Verificar se o arquivo está presente no dicionário files_parts_info
            matching_parts = [part for part in files_parts_info if part.startswith(file_request)]

            if matching_parts:
                # Obter informações sobre as partes do arquivo
                parts_info = [(part, files_parts_info[part][1], files_parts_info[part][0], files_parts_info[part][2])
                              for
                              part in matching_parts]

                # Criar uma lista de strings com a informação de cada parte
                parts_info_str_list = [f"{ip}" for part, ip, size, udp_port in parts_info]

                # Unir a lista em uma única string com delimitador '|'
                parts_info_str = '|'.join(parts_info_str_list)

                # Enviar o tamanho da resposta e a lista de partes ao cliente em um só pacote
                response_length = len(parts_info_str)
                print(f"\n\n\n{response_length}\n\n\n")
                response_length_bytes = response_length.to_bytes(3, byteorder='big')

                # Adicionar informações do arquivo ao pacote
                packet = response_length_bytes + parts_info_str.encode("utf-8") 
                # Enviar o pacote
                clientsocket.send(packet)
            else:
                # Se o arquivo solicitado não estiver presente, envie uma resposta indicando isso
                error_message = "File not available"
                error_message_bytes = error_message.encode("utf-8")
                length = len(error_message_bytes)

                length_bytes = length.to_bytes(2, byteorder='big')
                packet = length_bytes + error_message_bytes

                clientsocket.send(packet)

        elif message_type == 5:

            part_name_length_bytes = clientsocket.recv(2)
            part_name_length = int.from_bytes(part_name_length_bytes, byteorder='big')

            part_name_bytes = clientsocket.recv(part_name_length)
            part_name = part_name_bytes.decode('utf-8')

            # avisar cliente com o ip_sender(cliente que enviou o ficheiro) que o pacote foi recebido pelo outro cliente

            ip = address[0]
            part_name = ''.join(char for char in part_name if char.isprintable())

            file_name, dot = os.path.splitext(part_name)
            file_name, _ = part_name.split('_part')
            file_name_dot = file_name + dot

            # Adicione a parte ao dicionário files_parts_info
            if part_name in files_parts_info:
                size, existing_ips, udp_port = files_parts_info[part_name]
                ips_list = list(existing_ips)
                if ip not in ips_list:
                    ips_list.append(ip)
                files_parts_info[part_name] = (size, tuple(ips_list), udp_port)

            # Verificar se cliente tem as partes todas
            if file_name_dot in files_info:
                _, num_parts_expected, _, _ = files_info[file_name_dot]
                client_parts_count = sum(
                    1 for part in files_parts_info if part.startswith(file_name) and ip in files_parts_info[part][1])
                if client_parts_count >= num_parts_expected:

                    with files_lock:
                        if file_name_dot in files_info:
                            size, _, ips_list, udp_port = files_info[file_name_dot]
                            ips_list = list(ips_list)
                            if ip not in ips_list:
                                ips_list.append(ip)
                            files_info[file_name_dot] = (size, num_parts_expected, tuple(ips_list), udp_port)

                    #print(files_info)
                    #print(files_parts_info)
                    
                    #_ = clientsocket.recv(1024)
                    


def run_server(server_name, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    ip_address= socket.gethostbyname(server_name)
    
    server.bind((ip_address, int(port)))
    server.listen()

    files_lock = threading.Lock()
    connected_clients = []
    files_parts_info = {}
    files_info = {}
    available_files = set()

    while True:
        clientsocket, address = server.accept()
        print(f"Connected to {address}")
        connected_clients.append(address)

        client_handler = threading.Thread(target=handle_client, args=(
        clientsocket, address, files_info, files_parts_info, available_files, files_lock))
        client_handler.start()


def udp_receiver(udp_socket, directory):
    while True:
        # Receber o pacote por UDP
        packet, _ = udp_socket.recvfrom(HEADERSIZE)
        # Extrair informações do pacote
        part_name_length = int.from_bytes(packet[:2], byteorder='big')
        part_name = packet[2:2 + part_name_length].decode('utf-8')
        file_data = packet[2 + part_name_length:]

        part_name_cleaned = ''.join(char for char in part_name if char.isprintable())

        # Construir o caminho do diretório e arquivo
        file_directory = os.path.join(os.path.dirname(directory), f"{part_name_cleaned.split('_part')[0]}_parts")
        part_file_path = os.path.join(file_directory, part_name_cleaned)

        with lock:
            # Criar diretório se não existir
            if not os.path.exists(file_directory):
                os.makedirs(file_directory)

            # Salvar a parte do arquivo no diretório de download
            with open(part_file_path, 'wb') as part_file:
                part_file.write(file_data)
            with download_lock:
                temp_list_ip, temp_index, __ = download_dict[part_name_cleaned]
                queue_recv.put(part_name_cleaned)
                download_dict[part_name_cleaned] = (temp_list_ip, temp_index, 1)
        
            condition.notifyAll()


def udp_sender(udp_socket, udp_receive_socket, directory):
    while True:
        part_name, ip_address = udp_receive_socket.recvfrom(HEADERSIZE)
        part_name = part_name.decode('utf-8')

        port = ip_address[1]
        ip = ip_address[0]
        part_name_cleaned = ''.join(char for char in part_name if char.isprintable())

        _, part_aux = part_name_cleaned.split('_part')

        part_aux, _ = part_aux.split('.')

        file_directory = os.path.join(os.path.dirname(directory), f"{part_name_cleaned.split('_part')[0]}_parts")

        file_path = os.path.join(file_directory, part_name_cleaned)

        try:
            with open(file_path, 'rb') as file:
                # Leitura do conteúdo do arquivo
                file_data = file.read()

                # Construir o pacote com o part_name e file_data
                part_name_length = len(part_name_cleaned).to_bytes(2, byteorder='big')
                packet = part_name_length + part_name_cleaned.encode('utf-8') + file_data

                # Envio do arquivo por UDP
                udp_socket.sendto(packet, (ip, int(port) - 1))

                #print(f"Sent part {part_name} to {ip_address}")
        except FileNotFoundError:
            print(f"Error: File {part_name} not found")


def run_client(server_name, port, directory):
    
    os.environ['DISPLAY'] = ':0.0'
    
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #fcntl.fcntl(client, fcntl.F_SETFL, os.O_NONBLOCK)
    
    ip_address= socket.gethostbyname(server_name)
    
    client.connect((ip_address, int(port)))

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_port = 2000
    udp_socket.bind(("0.0.0.0", udp_port))

    udp_receive_port = udp_port + 1

    udp_receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receive_socket.bind(("0.0.0.0", udp_receive_port))

    # Inicie a thread para envio UDP
    udp_sender_thread = threading.Thread(target=udp_sender, args=(udp_socket, udp_receive_socket, directory))
    udp_sender_thread.daemon = True
    udp_sender_thread.start()

    # Inicie a thread para recebimento UDP
    udp_receiver_thread = threading.Thread(target=udp_receiver, args=(udp_socket, directory))
    udp_receiver_thread.daemon = True
    udp_receiver_thread.start()

    type_1(client, directory, port)
    # client.close()
    # client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # client.connect((ip_address, int(port)))
    host_name = socket.gethostname()
    root = Tk()
    root.title(host_name)
    
    frame = Frame(root, bg="#f0f0f0")
    
    # Adicione uma área de texto para exibir mensagens na interface gráfica
    text_area = Text(frame, wrap="word", width=40, height=10, font=("Helvetica", 12))
    text_area.grid(row=5, column=0, columnspan=2, pady=20)

    # Adicione uma barra de rolagem à área de texto
    scroll_bar = Scrollbar(frame, command=text_area.yview)
    scroll_bar.grid(row=5, column=2, sticky="nsew")
    text_area.config(yscrollcommand=scroll_bar.set)

    def view_files():
        type_2(client, text_area)

    def get_file_info():
        file_request = input("Enter the file you want to get information about: ")
        type_3(client, file_request, text_area)

    def download_file():
        type_4(client, udp_socket, udp_receive_socket, directory, udp_port)

    def exit_program():
        type_0(client)
        root.destroy()
        
    def clear_output(text_area):
        text_area.delete("1.0", END)

    

    # Adicione cor de fundo à janela principal
    root.configure(bg="#f0f0f0")

    
    frame.pack(padx=20, pady=20)

    # Adicione rótulo para título
    title_label = Label(frame, text="Menu Operations", font=("Helvetica", 16), bg="#f0f0f0")
    title_label.grid(row=0, column=0, columnspan=2, pady=10)

    # Adicione botões com cores diferentes
    view_files_button = Button(frame, text="View Available Files", command=view_files, bg="#4CAF50", fg="white")
    view_files_button.grid(row=1, column=0, pady=10)

    get_info_button = Button(frame, text="Get File Information", command=get_file_info, bg="#2196F3", fg="white")
    get_info_button.grid(row=1, column=1, pady=10)

    download_button = Button(frame, text="Download File", command=download_file, bg="#FF9800", fg="white")
    download_button.grid(row=2, column=0, columnspan=2, pady=10)
    
    clear_button = Button(frame, text="Clear Output", command=lambda: clear_output(text_area), bg="#607D8B", fg="white")
    clear_button.grid(row=3, column=0, columnspan=2, pady=10)  # Adjusted row position

    exit_button = Button(frame, text="Exit", command=exit_program, bg="#FF5722", fg="white")
    exit_button.grid(row=4, column=0, columnspan=2, pady=10)
    
    
    

    root.mainloop()

    udp_socket.close()
    udp_receive_socket.close()


def eliminar_diretoria(diretoria):
    try:
        # Remove todos os arquivos na diretoria
        for arquivo in os.listdir(diretoria):
            caminho_arquivo = os.path.join(diretoria, arquivo)
            if os.path.isfile(caminho_arquivo):
                os.unlink(caminho_arquivo)

        # Remove a própria diretoria
        os.rmdir(diretoria)

        print(f"A diretoria {diretoria} e os seus arquivos foram removidos com sucesso.")

    except Exception as e:
        print(f"Ocorreu um erro ao tentar eliminar a diretoria {diretoria}: {e}")


def split_file(file_path, chunk_size, output_directory):
    if os.path.isfile(file_path):
        file_name, file_extension = os.path.splitext(os.path.basename(file_path))
        file_parts_directory = os.path.join(output_directory, f"{file_name}_parts")  # Caminho de saída modificado
        if not os.path.exists(file_parts_directory):
            os.makedirs(file_parts_directory)
            with open(file_path, 'rb') as file:
                index = 1
                while True:
                    data = file.read(chunk_size)
                    # if index==1 and  len(data) < 10:
                    #     break
                    if not data:
                        break
                    part_file_name = f"{file_name}_part{index}{file_extension}"
                    with open(os.path.join(file_parts_directory, part_file_name), 'wb') as part_file:
                        part_file.write(data)
                    index += 1


def concatenate_file_parts(file_name, directory):
    file_and_parts_directory = os.path.dirname(directory)

    name, dot = file_name.split('.')

    parts_name = name + "_parts"

    part_name_cleaned = ''.join(char for char in parts_name if char.isprintable())

    parts_directory = os.path.join(file_and_parts_directory, part_name_cleaned)

    # Get the list of part files in the parts directory
    part_files = [part_file for part_file in os.listdir(parts_directory) if part_file.startswith(name)]

    # Sort the part files based on their index in the filename
    part_files.sort(key=lambda x: int(x.split("_part")[1].split(".")[0]))

    # Create the full file path for the joined file
    joined_file_path = os.path.join(directory, file_name)

    # Open the joined file in binary write mode
    with open(joined_file_path, 'wb') as joined_file:
        # Iterate through the parts and append their content to the joined file
        for part_file_name in part_files:
            part_file_path = os.path.join(parts_directory, part_file_name)
            with open(part_file_path, 'rb') as part_file:
                joined_file.write(part_file.read())

    print(f"Concatenated file saved at: {joined_file_path}")


def type_0(client):
    termination_message_type = 0
    termination_message_type_bytes = termination_message_type.to_bytes(1, byteorder='big')
    client.send(termination_message_type_bytes)
    print("Termination message sent. Exiting client.")
    client.close()


def type_1(client, directory, port):
    message_type = 1

    files_list = [file for file in os.listdir(directory) if not file.startswith('.')]
    files_list.sort()


    for file in files_list:
        file_name, _ = os.path.splitext(file)
        file_directory = os.path.dirname(directory)
        split_file(os.path.join(directory, file), PARTSIZE, file_directory)
        

    # Delimiters added here
    files_list_str = '|'.join([f"{file},{os.path.getsize(os.path.join(directory, file))}" for file in files_list]) + '|'

    files_list_bytes = files_list_str.encode("utf-8")

    length = len(files_list_bytes)

    message_type_bytes = message_type.to_bytes(1, byteorder='big')
    length_bytes = length.to_bytes(3, byteorder='big')

    port_udp = 2000
    port_bytes = port_udp.to_bytes(2, byteorder='big')

    # Modified packets with delimiters

    packet = message_type_bytes + length_bytes  + port_bytes + files_list_bytes

    client.send(packet)


def type_2(client, text_area):
    message_type = 2
    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes

    client.send(packet)

    # Receive the list of available files from the server
    length_bytes = client.recv(2)
    length = int.from_bytes(length_bytes, byteorder='big')

    available_files_bytes = client.recv(length)
    available_files_str = available_files_bytes.decode("utf-8")
    available_files = available_files_str.split('|')
    

    text_area.insert("end", f"Available files: {available_files}\n")

    



def type_3(client, file_request, text_area):
    message_type = 3

    if not file_request:
        file_request = input("Enter the file you want to get information about: ")

    file_lenght = len(file_request)
    file_lenght_bytes = file_lenght.to_bytes(2, byteorder='big')

    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes + file_lenght_bytes + file_request.encode("utf-8")
    client.send(packet)

    response_length_bytes = client.recv(2)
    response_length = int.from_bytes(response_length_bytes, byteorder='big')

    # Recebendo a resposta do servidor
    received_data = client.recv(response_length)

    # Decodificando a string JSON para um dicionário
    response_data = json.loads(received_data.decode("utf-8"))

    if response_data.get(file_request):
        # Extraindo informações do dicionário de resposta
        file_size, num_parts, ips_list, _ = response_data[file_request]

        # Convertendo a lista de IPs em uma string formatada
        locations = ', '.join(ips_list)
        
        text_area.insert("end", f"\nFile Information: {file_request}\n")
        text_area.insert("end", f"Size: {file_size} bytes\nNumber of Parts: {num_parts}\nLocations: {locations}\n")
    else:
        # Adicione a mensagem abaixo de todas as linhas existentes
        text_area.insert("end", f"\nFile not found: {file_request}\n")



def type_4(client, udp_socket, udp_receive_socket, directory, udp_port):
    file_request = input("Enter the file name to Download: ")
    
    message_type = 4
    file_length = len(file_request)
    file_length_bytes = file_length.to_bytes(2, byteorder='big')

    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes + file_length_bytes + file_request.encode("utf-8")
    client.send(packet)

    response_length_bytes = client.recv(3)
    response_length = int.from_bytes(response_length_bytes, byteorder='big')

    print(f"\n\n\n{response_length}\n\n\n")
    # Receber a resposta do servidor
    received_data = client.recv(response_length)
    response_data = received_data.decode("utf-8")
    
    print(f"\n\nRECEVVID\n{response_data}\n")

    i = 0
    len_aux = 0

    # Se a resposta indicar que o arquivo não foi encontrado, imprimir a mensagem
    if response_data == "File not available":
        print("File not found")
    else:
        parts_info_list = response_data.split('|')
        # Iterar sobre as partes e enviar mensagens UDP para cada cliente
        h=0
        part,dot = file_request.split('.')
                    
        for part_info in parts_info_list:
            ip_list = eval(part_info)
            part_name = f"{part}_part{h + 1}.{dot}"
            h +=1

            udp_message_type = 1
            udp_message_type_bytes = udp_message_type.to_bytes(1, byteorder='big')
            part_name_bytes = part_name.encode("utf-8")

            packet = udp_message_type_bytes + part_name_bytes
            
            if i == 0:
                len_aux = len(ip_list)

            index_ip = random.randint(0, len_aux - 1)

            ip = ip_list[index_ip]
            key = part_name
            value = (ip_list, index_ip, 0)
            #print(key)
            with download_lock:
                download_dict[key] = value
            i = i + 1
            

            # Enviar mensagem UDP para o cliente específico
            udp_receive_socket.sendto(packet, (ip, udp_port + 1))
            #print(f"Sent UDP request for part {part_name} to {ip}:{udp_port}")
            

            # Adicionar o download da parte ao download_dict

    control_download = 1
    tamanho = 0
    flag_aux = 0
    q=-1
    while tamanho < i:
        with lock:

            reason = condition.wait(timeout=1)

            if reason or q==0:
                #print(f"tamanho: {tamanho}")
                #print(f"i: {i}")
                tamanho = tamanho + queue_recv.qsize()
                for t in range(queue_recv.qsize()):
                    part_name = queue_recv.get()
                    print(part_name)
                    try:
                        message_type = 5
                        message_type_bytes = message_type.to_bytes(1, byteorder='big')
                        part_name_bytes = part_name.encode('utf-8')

                        part_size = len(part_name)
                        part_size_bytes = part_size.to_bytes(2, byteorder='big')

                        # Criar o pacote com o tipo de mensagem e o nome da parte
                        packet = message_type_bytes + part_size_bytes + part_name_bytes

                        client.send(packet)
                        q=-1
                    except Exception as e:
                        print(f"Erro ao enviar pacote: {e}")

            else:
                print(f"Control Download:{control_download}")
                if control_download == 30:
                    file_parts_directory = os.path.join(os.path.dirname(directory),
                                                        f"{part_name.split('_part')[0]}_parts")
                    eliminar_diretoria(file_parts_directory)
                    print(
                        f"Download Error, Unable to Download all the parts of the {file_request}. File Corrupted or not Available. Try again")
                    flag_aux = 1

                    break
                with download_lock:
                    q=0
                    for key, values in download_dict.items():
                        
                        ip_list, index_ip, flag = values

                        if flag == 0:
                            q +=1
                            try:
                                udp_message_type = 1
                                udp_message_type_bytes = udp_message_type.to_bytes(1, byteorder='big')
                                part_name_bytes = key.encode("utf-8")

                                packet = udp_message_type_bytes + part_name_bytes

                                len_aux = len(ip_list)

                                if len_aux > 1:
                                    for y in range(2):
                                        if y != index_ip:
                                            ip = ip_list[y]
                                            udp_receive_socket.sendto(packet, (ip, int(udp_port) + 1))
                                            break
                            except Exception as e:
                                print(f"Erro ao enviar pacote: {e}")
                            else:
                                try:
                                    ip = ip_list[index_ip]
                                    udp_receive_socket.sendto(packet, (ip, int(udp_port) + 1))
                                except Exception as e:
                                    print(f"Erro ao enviar pacote: {e}")
                    control_download += 1

    if flag_aux == 0:
        concatenate_file_parts(file_request, directory)
        
    
            
            



def print_usage():
    print("===========================================================================")
    print("INVALID ARGUMENTS")
    print("USAGE...")
    print("---------------------------------------------------------------------------")
    print("Run as a server: 1 [ip address] [port]")
    print("---------------------------------------------------------------------------")
    print("Run as a client: 2 [ip address (server)] [port] [directory]")
    print("===========================================================================")


if __name__ == "__main__":

    try:
        lock = threading.Lock()
        download_lock = threading.Lock()
        condition = threading.Condition(lock)
        is_server = False

        # Check if the script is run as a server or a client
        if (sys.argv[1] == "help"):
            print_usage()

        if len(sys.argv) == 4 and sys.argv[1] == '1':
            # Run the server with the specified IP address
            is_server = True
            run_server(sys.argv[2], sys.argv[3])

        elif len(sys.argv) == 5 and sys.argv[1] == '2':
            run_client(sys.argv[2], sys.argv[3], sys.argv[4])

        else:
            print_usage()

    # except KeyboardInterrupt:
    # if os.name == 'posix':
    # os.system('clear')
    # elif os.name == 'nt':
    # os.system('cls')
    # print("Program interrupted. Terminal cleared.")

    except KeyboardInterrupt:

        if (is_server):
            print("\n\n=========================")
            print("Server interrupted.")
            print("=========================\n")

        else:
            print("\n\n=========================")
            print("Client interrupted.")
            print("=========================\n")

        sys.exit(0)