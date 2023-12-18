import socket
import os
import sys
import threading
import json
import queue
import random
import time
from tkinter import Tk, Label, Button, Frame, Text, Scrollbar, Entry, END, simpledialog
from time import sleep
import hashlib

PARTSIZE = 64000
global download_lock
global lock
HEADERSIZE = 64100
global condition
queue_recv = queue.Queue()
download_dict = {}


def handle_client(clientsocket, address, files_info, files_parts_info, available_files, files_lock):
    while True:

        message_type_bytes = clientsocket.recv(1)


        message_type = int.from_bytes(message_type_bytes, byteorder='big')

        if message_type == 0:

            print(f"Connection from {address} terminated.")

            name,_,_ = socket.gethostbyaddr(address[0])
            name,_,_ = name.split('.')

            
            with files_lock:
                for file, info in list(files_info.items()):
                    size, num_parts, names, port_udp , hash = info
                    names_list = list(names)

                    if name in names_list:
                        names_list.remove(name)
                        
                        if len(names_list) == 0:
                            available_files.discard(file)
                            
                            del files_info[file]
                        else:
                            files_info[file] = size, num_parts, names_list, port_udp , hash

                for part, info in list(files_parts_info.items()):
                    size, names, port_udp = info
                    names_list = list(names)
                    
                    if name in names_list:
                        names_list.remove(name)
                        files_parts_info[part] = (info[0], tuple(names_list), info[2])

                        if len(names_list) == 0:
                            del files_parts_info[part]
                        else:
                            files_parts_info[part]= size, names_list, port_udp
            clientsocket.close()
            break


        elif message_type == 1:
            
            length_temp = clientsocket.recv(3)
            list_length = int.from_bytes(length_temp, byteorder='big')

            port_temp = clientsocket.recv(2)
            port_udp = int.from_bytes(port_temp, byteorder='big')

            
            msg = clientsocket.recv(list_length)
            
            files_data = msg.decode("utf-8").split('|')
            files_data = list(filter(None, files_data))
            
            names_list = []
            file_parts_aux = []
            with files_lock:

                
                for file in files_data:
                    file, size, hash = file.split(',')
                    file_name, dot = file.split('.')
                    
                    name,_,_ = socket.gethostbyaddr(address[0])
                    name,_,_ = name.split('.')

                    num_parts_aux = int(size) // PARTSIZE
                    last_part_size = int(size) % PARTSIZE

                    
                    file_parts_aux.extend([
                        f"{file_name}_part{i + 1}.{dot},{PARTSIZE}" for i in range(num_parts_aux)
                    ])

                    if num_parts_aux == 0 or last_part_size > 0:
                        file_parts_aux.append(f"{file_name}_part{num_parts_aux + 1}.{dot},{last_part_size}")
                        
                    if file in files_info:
                        _,_,names,port_udp, _ = files_info[file]
                        names_list = list(names)
                        if name not in names_list:
                            names_list.append(name)
                            
                        files_info[file] = (int(size), num_parts_aux + 1, tuple(names_list), port_udp, hash)
                    else:
                        files_info[file] = (int(size), num_parts_aux + 1, [name], port_udp, hash)


                names_list_parts = []

                
                for item in file_parts_aux:
                    part, size = item.split(',')
                    file_name, part_num = part.split('_part')
        
                    name,_,_ = socket.gethostbyaddr(address[0])
                    name,_,_ = name.split('.')
                    
                    part_key = f"{file_name}_part{part_num}" 
                                          
                    if part_key in files_parts_info:
                        
                        _, existing_names, _ = files_parts_info[part_key]
                        
                        names_list_parts = list(existing_names)  
                        if name not in names_list_parts:
                            names_list_parts.append(name)
                        
                        files_parts_info[part_key] = (int(size), tuple(names_list_parts), port_udp)
                    else:
                        files_parts_info[part_key] = (int(size), [name], port_udp)
                    
                    for file in files_data:
                        file_name, _, hash = file.split(',')
                        available_files.add(file_name)

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
            
            if file_request in files_info:
                data = files_info[file_request]
            

            response_data = json.dumps(data)
    
            response_length = len(response_data)
            response_length_bytes = response_length.to_bytes(2, byteorder='big')

            packet = response_length_bytes + response_data.encode("utf-8")

            
            clientsocket.send(packet)

        elif message_type == 4:

            file_length = clientsocket.recv(2)
            file_length = int.from_bytes(file_length, byteorder='big')

            file_request = clientsocket.recv(file_length).decode("utf-8")

            file_aux, _ = file_request.split(".")
                

            with files_lock:
                
                matching_parts = [part for part in files_parts_info if part.startswith(file_aux)]
                
                num_parts = len(matching_parts)
                
                loop_number = int(num_parts/200)
                aux = num_parts%200
                if aux:
                    loop_number += 1
                if loop_number == 1:
                    parts_info = [(part, files_parts_info[part][1], files_parts_info[part][0], files_parts_info[part][2]) for part in matching_parts]

                    
                    parts_info_str_list = [f"{name_list}" for _, name_list, _, _ in parts_info]

                    
                    parts_info_str = '|'.join(parts_info_str_list)

                    
                    response_length = len(parts_info_str)
                    response_length_bytes = response_length.to_bytes(3, byteorder='big')
                    
                    
                    if file_request in files_info:
                        _, _, _, _, hash = files_info[file_request]
                    
                    hash_length = len(hash)
                    hash_length_bytes = hash_length.to_bytes(2, byteorder='big')

                    
                    packet = response_length_bytes + hash_length_bytes + parts_info_str.encode("utf-8") + hash.encode("utf-8")
                    
                    clientsocket.send(packet)
                    
                    _ = clientsocket.recv(1)
                else:
                    i=1
                    while i<=loop_number:
                        
                        if i==1:
                            first_200_parts = matching_parts[:200]
                            parts_info = [(part, files_parts_info[part][1], files_parts_info[part][0], files_parts_info[part][2]) for part in first_200_parts]
                            parts_info_str_list = [f"{name_list}" for _, name_list, _, _ in parts_info]
                            parts_info_str = '|'.join(parts_info_str_list)
                            
                            response_length = len(parts_info_str)
                            response_length_bytes = response_length.to_bytes(3, byteorder='big')
                            
                            if file_request in files_info:
                                _, _, _, _, hash = files_info[file_request]
                                
                            hash_length = len(hash)
                            hash_length_bytes = hash_length.to_bytes(2, byteorder='big')
                            
                            packet = response_length_bytes + hash_length_bytes + parts_info_str.encode("utf-8") + hash.encode("utf-8")
                            
                            clientsocket.send(packet)
                            
                            _ = clientsocket.recv(1)
                            
                        elif i==loop_number:
                            
                            if aux:
                                t=i-1
                                t=t*200
                                x=t+aux
                                parts = matching_parts[t:x]
                                parts_info = [(part, files_parts_info[part][1], files_parts_info[part][0], files_parts_info[part][2]) for part in parts]
                                parts_info_str_list = [f"{name_list}" for _, name_list, _, _ in parts_info]
                                parts_info_str = '|'.join(parts_info_str_list)
                            
                                response_length = len(parts_info_str)
                                response_length_bytes = response_length.to_bytes(3, byteorder='big')
                            
                                packet = response_length_bytes + parts_info_str.encode("utf-8")
                            
                                clientsocket.send(packet)
                            
                                _ = clientsocket.recv(1)
                                
                            else:
                                t=i-1
                                t=t*200
                                x=t+200
                                parts = matching_parts[t:x]
                                parts_info = [(part, files_parts_info[part][1], files_parts_info[part][0], files_parts_info[part][2]) for part in parts]
                                parts_info_str_list = [f"{name_list}" for _, name_list, _, _ in parts_info]
                                parts_info_str = '|'.join(parts_info_str_list)
                            
                                response_length = len(parts_info_str)
                                response_length_bytes = response_length.to_bytes(3, byteorder='big')
                        
                                packet = response_length_bytes + parts_info_str.encode("utf-8")
                            
                                clientsocket.send(packet)
                            
                                _ = clientsocket.recv(1)
                        
                        else:
                            
                            t=i-1
                            t=t*200
                            x=t+200
    
                            parts = matching_parts[t:x]
                            parts_info = [(part, files_parts_info[part][1], files_parts_info[part][0], files_parts_info[part][2]) for part in parts]
                            parts_info_str_list = [f"{name_list}" for _, name_list, _, _ in parts_info]
                            parts_info_str = '|'.join(parts_info_str_list)
                        
                            response_length = len(parts_info_str)
                            response_length_bytes = response_length.to_bytes(3, byteorder='big')
                        
                            packet = response_length_bytes + parts_info_str.encode("utf-8")
                        
                            clientsocket.send(packet)
                        
                            _ = clientsocket.recv(1)
                            
                        i+=1
                
          
        elif message_type == 5:

            part_name_length_bytes = clientsocket.recv(2)
            part_name_length = int.from_bytes(part_name_length_bytes, byteorder='big')

            part_name_bytes = clientsocket.recv(part_name_length)
            part_name = part_name_bytes.decode('utf-8')

            
            name,_,_ = socket.gethostbyaddr(address[0])
            name,_,_ = name.split('.')
            
            part_name = ''.join(char for char in part_name if char.isprintable())

            file_name, dot = os.path.splitext(part_name)
            file_name, _ = part_name.split('_part')
            file_name_dot = file_name + dot

            with files_lock:
                if part_name in files_parts_info:
                    size, existing_names, udp_port = files_parts_info[part_name]
                    names_list = list(existing_names)
                    if name not in names_list:
                        names_list.append(name)
                    files_parts_info[part_name] = (size, tuple(names_list), udp_port)

            
                if file_name_dot in files_info:
                    _, num_parts_expected, _, _, hash = files_info[file_name_dot]
                    client_parts_count = sum(
                        1 for part in files_parts_info if part.startswith(file_name) and name in files_parts_info[part][1])
                    
                    if client_parts_count >= num_parts_expected:
                        size, _, names_list, udp_port, hash = files_info[file_name_dot]
                        names_list = list(names_list)
                        if name not in names_list:
                            names_list.append(name)
                        files_info[file_name_dot] = (size, num_parts_expected, tuple(names_list), udp_port, hash)
        
        elif message_type == 6:
            file_name_length_bytes = clientsocket.recv(2)
            file_name_length = int.from_bytes(file_name_length_bytes, byteorder='big')

            file_name_bytes = clientsocket.recv(file_name_length)
            file_name = file_name_bytes.decode('utf-8')

            name,_,_ = socket.gethostbyaddr(address[0])
            name,_,_ = name.split('.')


            with files_lock:
                if file_name in files_info:
                    
                    size, num_parts, names, port_udp , hash = files_info[file_name]
                    names_list = list(names)

                    if name in names_list:
                        names_list.remove(name)
                        
                        if len(names_list) == 0:
                            available_files.discard(file)
                            
                            del files_info[file]
                        else:
                            files_info[file] = size, num_parts, names_list, port_udp , hash

                
                for part, info in list(files_parts_info.items()):
                         
                    file_aux,_ = file_name.split('.')
                    if part.startswith(file_aux):
                        size, names, port_udp = info
                        names_list = list(names)
                        
                        if name in names_list:
                            names_list.remove(name)
                            files_parts_info[part] = (info[0], tuple(names_list), info[2])
                            if len(names_list) == 0:
                                del files_parts_info[part]
                            else:
                                files_parts_info[part]= size, names_list, port_udp
            
            


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
        
        packet, _ = udp_socket.recvfrom(HEADERSIZE)
        
        part_name_length = int.from_bytes(packet[:2], byteorder='big')
        part_name = packet[2:2 + part_name_length].decode('utf-8')
        file_data = packet[2 + part_name_length:]

        part_name_cleaned = ''.join(char for char in part_name if char.isprintable())

        
        file_directory = os.path.join(os.path.dirname(directory), f"{part_name_cleaned.split('_part')[0]}_parts")
        part_file_path = os.path.join(file_directory, part_name_cleaned)

        with lock:
            
            if not os.path.exists(file_directory):
                os.makedirs(file_directory)

            
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
                
                file_data = file.read()

                part_name_length = len(part_name_cleaned).to_bytes(2, byteorder='big')
                packet = part_name_length + part_name_cleaned.encode('utf-8') + file_data

                
                udp_socket.sendto(packet, (ip, int(port) - 1))

        except FileNotFoundError:
            print(f"Error: File {part_name} not found")
            


def run_client(server_name, port, directory):
    
    os.environ['DISPLAY'] = ':0.0'
    
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    ip_address= socket.gethostbyname(server_name)
    
    client.connect((ip_address, int(port)))

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_port = 2000
    udp_socket.bind(("0.0.0.0", udp_port))

    udp_receive_port = udp_port + 1

    udp_receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receive_socket.bind(("0.0.0.0", udp_receive_port))
    
    for y in range(20):
        
        udp_sender_thread = threading.Thread(target=udp_sender, args=(udp_socket, udp_receive_socket, directory))
        udp_sender_thread.daemon = True
        udp_sender_thread.start()
        
        udp_receiver_thread = threading.Thread(target=udp_receiver, args=(udp_socket, directory))
        udp_receiver_thread.daemon = True
        udp_receiver_thread.start()

    type_1(client, directory, port)
    host_name = socket.gethostname()
    root = Tk()
    root.title(host_name)
    
    frame = Frame(root, bg="#f0f0f0")
    
    text_area = Text(frame, wrap="word", width=40, height=10, font=("Helvetica", 12))
    text_area.grid(row=5, column=0, columnspan=2, pady=20)

    scroll_bar = Scrollbar(frame, command=text_area.yview)
    scroll_bar.grid(row=5, column=2, sticky="nsew")
    text_area.config(yscrollcommand=scroll_bar.set)

    def view_files():
        type_2(client, text_area)

    def get_file_info():
        type_3(client, text_area, host_name)

    def download_file():
        type_4(client, udp_receive_socket, directory, udp_port, text_area, host_name)

    def exit_program():
        type_0(client)
        root.destroy()
        
    def clear_output(text_area):
        text_area.delete("1.0", END)

    

    root.configure(bg="#f0f0f0")

    
    frame.pack(padx=20, pady=20)

    title_label = Label(frame, text="Menu Operations", font=("Helvetica", 16), bg="#f0f0f0")
    title_label.grid(row=0, column=0, columnspan=2, pady=10)

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
    
def sha1(nome_arquivo, tamanho_do_bloco):
    sha1 = hashlib.sha1()

    with open(nome_arquivo, 'rb') as arquivo:
        bloco = arquivo.read(tamanho_do_bloco)
        while len(bloco) > 0:
            sha1.update(bloco)
            bloco = arquivo.read(tamanho_do_bloco)

    return sha1.hexdigest()

def eliminar_diretoria(diretoria):
    try:
        for arquivo in os.listdir(diretoria):
            caminho_arquivo = os.path.join(diretoria, arquivo)
            if os.path.isfile(caminho_arquivo):
                os.unlink(caminho_arquivo)

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

    part_files = [part_file for part_file in os.listdir(parts_directory) if part_file.startswith(name)]

    part_files.sort(key=lambda x: int(x.split("_part")[1].split(".")[0]))

    joined_file_path = os.path.join(directory, file_name)

    with open(joined_file_path, 'wb') as joined_file:
        for part_file_name in part_files:
            part_file_path = os.path.join(parts_directory, part_file_name)
            with open(part_file_path, 'rb') as part_file:
                joined_file.write(part_file.read())



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
        

    files_list_str = '|'.join([f"{file},{os.path.getsize(os.path.join(directory, file))},{sha1(os.path.join(directory, file),os.path.getsize(os.path.join(directory, file)))}" for file in files_list]) + '|'

    files_list_bytes = files_list_str.encode("utf-8")

    length = len(files_list_bytes)

    message_type_bytes = message_type.to_bytes(1, byteorder='big')
    length_bytes = length.to_bytes(3, byteorder='big')

    port_udp = 2000
    port_bytes = port_udp.to_bytes(2, byteorder='big')


    packet = message_type_bytes + length_bytes  + port_bytes + files_list_bytes

    client.send(packet)


def type_2(client, text_area):
    message_type = 2
    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes

    client.send(packet)

    length_bytes = client.recv(2)
    length = int.from_bytes(length_bytes, byteorder='big')

    available_files_bytes = client.recv(length)
    available_files_str = available_files_bytes.decode("utf-8")
    available_files = available_files_str.split('|')
    
    if text_area!=None:
        text_area.insert("end", f"Available files: {available_files}\n")
    else: 
        return available_files

    
def type_3(client, text_area, host_name,file_request=None):
    
    available_files = type_2(client,None)
    message_type = 3
    if text_area!=None: 
        file_request=None
        while file_request not in available_files:
            file_request = simpledialog.askstring(f"{host_name}","Enter the file you want to get information about:")
            if file_request is None:
                return
            
            if file_request not in available_files:
                text_area.insert(END, f"Invalid file request: {file_request}\n")
                text_area.see(END)  # Ensure that the inserted text is visible
        

    file_lenght = len(file_request)
    file_lenght_bytes = file_lenght.to_bytes(2, byteorder='big')

    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes + file_lenght_bytes + file_request.encode("utf-8")
    client.send(packet)

    response_length_bytes = client.recv(2)
    response_length = int.from_bytes(response_length_bytes, byteorder='big')

    received_data = client.recv(response_length)

    response_data = json.loads(received_data.decode("utf-8"))

    file_size, num_parts, names_list, _, hash = response_data

    locations = ', '.join(names_list)
        
    if text_area!=None:   
        text_area.insert("end", f"\nFile Information: {file_request}\n")
        text_area.insert("end", f"Size: {file_size} bytes\nNumber of Parts: {num_parts}\nLocations: {locations}\n")
    else:
         
        return response_data


def type_4(client, udp_receive_socket, directory, udp_port, text_area, host_name):
    available_files = type_2(client,None)
    
    file_request = None
    while file_request not in available_files:
        file_request = simpledialog.askstring(f"{host_name}", "Enter the file name to Download:")
        if file_request is None:
            return
        # Check if the entered file_request is valid
        if file_request not in available_files:
            text_area.insert(END, f"Invalid file request: {file_request}\n")
            text_area.see(END)  # Ensure that the inserted text is visible
        
    response = type_3(client,None,host_name, file_request)
    _, num_parts, _, _, _ = response
    message_type = 4
    file_length = len(file_request)
    file_length_bytes = file_length.to_bytes(2, byteorder='big')

    message_type_bytes = message_type.to_bytes(1, byteorder='big')

    packet = message_type_bytes + file_length_bytes + file_request.encode("utf-8")
    client.send(packet)
    
    loop_number = int(num_parts/200)
    aux = num_parts%200
    full_str = None
    
    if aux:
        loop_number += 1
        
    if loop_number==1:
        
        response_length_bytes = client.recv(3)
        response_length = int.from_bytes(response_length_bytes, byteorder='big')
    
        hash_length_bytes = client.recv(2)
        hash_length = int.from_bytes(hash_length_bytes, byteorder='big')

        received_data = client.recv(response_length)
        response_data = received_data.decode("utf-8")
        
        hash_data = client.recv(hash_length)
        received_hash = hash_data.decode("utf-8")
        
        full_str = response_data
        
        confirmation=1
        
        confirmation_bytes = confirmation.to_bytes(1, byteorder='big')
        
        client.send(confirmation_bytes)
        
        
    else:
        r=1
        while r<=loop_number:
            
            if r==1:
                response_length_bytes = client.recv(3)
                response_length = int.from_bytes(response_length_bytes, byteorder='big')
    
                hash_length_bytes = client.recv(2)
                hash_length = int.from_bytes(hash_length_bytes, byteorder='big')

                received_data = client.recv(response_length)
                response_data = received_data.decode("utf-8")
            
                hash_data = client.recv(hash_length)
                received_hash = hash_data.decode("utf-8")
                
                full_str = response_data
            
                confirmation=1
            
                confirmation_bytes = confirmation.to_bytes(1, byteorder='big')
            
                client.send(confirmation_bytes)
                
                
                
            else:
                
                response_length_bytes = client.recv(3)
                response_length = int.from_bytes(response_length_bytes, byteorder='big')
                
                received_data = client.recv(response_length)
                response_data = received_data.decode("utf-8")
                
                full_str = full_str +'|'+ response_data
                
                confirmation=1
            
                confirmation_bytes = confirmation.to_bytes(1, byteorder='big')
            
                client.send(confirmation_bytes)
            r+=1
        
    len_aux = 0

    
    if full_str == "File not available":
        print("File not found")
    else:
        parts_info_list = full_str.split('|')
        i=len(parts_info_list)
        part,dot = file_request.split('.')
        h=0
        for part_info in parts_info_list:
            names_list = eval(part_info)
            part_name = f"{part}_part{h + 1}.{dot}"
            h +=1

            part_name_bytes = part_name.encode("utf-8")

            packet = part_name_bytes
            
            if h == 1:
                len_aux = len(names_list)

            index_name = random.randint(0, len_aux - 1)

            name = names_list[index_name]
            key = part_name
            value = (names_list, index_name, 0)
            
            with download_lock:
                download_dict[key] = value
            
            udp_receive_socket.sendto(packet, (socket.gethostbyname(name), udp_port + 1))
        
    control_download = 1
    tamanho = 0
    flag_aux = 0
    q=-1
    while tamanho < i:
        with lock:

            reason = condition.wait(timeout=1)

            if reason or q==0:
                
                tamanho = tamanho + queue_recv.qsize()
                for t in range(queue_recv.qsize()):
                    part_name = queue_recv.get()
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
                        
                        names_list, index_name, flag = values

                        if flag == 0:
                            q +=1
                            try:
                                
                                part_name_bytes = key.encode("utf-8")

                                packet = part_name_bytes

                                len_aux = len(names_list)

                                if len_aux > 1:
                                    for y in range(2):
                                        if y != index_name:
                                            name = names_list[y]
                                            udp_receive_socket.sendto(packet, (socket.gethostbyname(name), int(udp_port) + 1))
                                            break
                            except Exception as e:
                                print(f"Erro ao enviar pacote: {e}")
                            else:
                                try:
                                    name = names_list[index_name]
                                    udp_receive_socket.sendto(packet, (socket.gethostbyname(name), int(udp_port) + 1))
                                except Exception as e:
                                    print(f"Erro ao enviar pacote: {e}")
                    control_download += 1

    if flag_aux == 0:
        concatenate_file_parts(file_request, directory)
        
    file_path = f"{directory}/{file_request}"
    file_size = os.path.getsize(file_path)

    hash = sha1(file_path,file_size)
    
    if hash == received_hash:
        text_area.insert("end",f"File saved at: {file_path}")
    else:
        file_parts_directory = os.path.join(os.path.dirname(directory),f"{file_request.split('.')[0]}_parts")
        eliminar_diretoria(file_parts_directory)
        os.rmdir(file_path)

        message_type = 6
        message_type_bytes = message_type.to_bytes(1, byteorder='big')
        part_name_bytes = file_request.encode('utf-8')

        part_size = len(file_request)
        part_size_bytes = part_size.to_bytes(2, byteorder='big')

        # Criar o pacote com o tipo de mensagem e o nome da parte
        packet = message_type_bytes + part_size_bytes + part_name_bytes

        client.send(packet)
        text_area.insert("end",f"Download Error. Hashed checksum doesn't match. Try again") 
        
    
    



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
