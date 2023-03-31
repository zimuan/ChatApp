import sys
from socket import *
import time
import threading
import json

cur_group = []
reg_success = False
dereg_ack_received = False
ack_server = False
ack_group = {}
ack_rcv = {}


def dict_to_str_with_msg(dic, header):
    """
    The function casts the given dictionary to a string for
    (usually server) to pass over through a message.

    :param dic: the dictionary (table to pass in)
    :param header: intended header message
    :return: msg: message to send
    """
    info = json.dumps({user: values for (user, values) in dic.items()})
    msg = f"header:{header}\n" + f"msg:{info}\n"
    return msg


def client_update(server_table, clients):
    """
    The function receives server table from server and updates
    new registerd clients, online status, and group/normal mode
    on client side table.

    :param server_table: server side dictionary
    :param clients: client side dictionary
    :return: None
    """
    global ack_rcv
    for user in server_table.keys():
        # update newly registered user
        if user not in clients.keys():
            clients[user] = server_table[user]
            # use ack_rcv dict to indicate whether received someone's ack when chatting
            ack_rcv[user] = False
        # update online status and mode
        else:
            if clients[user][2] != server_table[user][2]:
                clients[user][2] = server_table[user][2]
            if clients[user][3] != server_table[user][3]:
                clients[user][3] = server_table[user][3]


def broadcast(server_socket, clients, msg):
    """
    The function uses server_socket to broadcast given msg
    to all online clients given in the dictionary clients.

    :param server_socket: server socket to send message
    :param clients: dictionary
    :param msg: message to send
    :return: None
    """
    for user in clients:
        # only broadcast msg to online users
        if clients[user][2] == True:
            cur_user_ip = clients[user][0]
            cur_user_port = clients[user][1]
            server_socket.sendto(msg.encode(), (cur_user_ip, cur_user_port))


def serverRespond(msg, server_socket, target_addr, target_port):
    """
    The function simply sends a response (msg) from server to the
    client given its' (IP, port) through server socket.

    :param msg: message to send
    :param server_socket: server socket to send message
    :param target_addr: client's IP address
    :param target_port: client's listening port number
    :return: None
    """
    server_socket.sendto(msg.encode(), (target_addr, target_port))


def clientListen(client_socket, clients, stop_event, msg_queue):
    # declare new socket since previous one is used to send
    """
    The function serves as the 'listening' mode of client
    through another thread, while the main thread of client
    waits for client input.

    It kept listening from both server and clients until the
    client de-registers. While listening, the function
    behaves accordingly to the header given.

    :param client_socket: client socket
    :param clients: dictionary from client side
    :param stop_event: controls whether to kill current thread
    :return: None
    """
    global cur_group
    global reg_success
    global dereg_ack_received
    global ack_rcv
    global ack_server
    global ack_group

    # Stops listening when client de-reg
    while not stop_event.is_set():
        try:
            buffer, sender_address = client_socket.recvfrom(4096)
        except:
            continue
        buffer = buffer.decode()
        lines = buffer.splitlines()
        header = lines[0].split(":")[1]

        if header == 'reg':
            ack_server = True
            success = lines[1].split(":")[1]
            if success == "True":
                reg_success = True
                print(">>> [Welcome, You are registered.]")
            else:
                print(">>> Username is already registered, please try again. Exiting.")

        if header == 'dereg':
            dereg_ack_received = True
            break

        # for sending back an ack when received message
        if header == 'send':
            sender = lines[1].split(":")[1]
            receiver = lines[2].split(":")[1]
            message = lines[-1].split(":")[1]

            if clients[receiver][3] == 'Group':
                buffer_msg = f">>> {sender}: {message}"

                # since multiple users might perform 'write' operation to the queue
                # we use locking mechanism to prevent data race
                lock = threading.Lock()
                lock.acquire()
                try:
                    # Perform write operation here
                    msg_queue.append(buffer_msg)
                finally:
                    # Release the lock
                    lock.release()
            else:
                # prints the message on receiver's terminal
                print(f">>> {sender}: {message}")

            # sends an ack to sender
            ack_msg = f"header:ack\n" + f"user:{receiver}"
            client_socket.sendto(ack_msg.encode(), (clients[sender][0], clients[sender][1]))

        # received ack from receiver and change ack flag in DM
        if header == 'ack':
            # received ack from receiver
            receiver = lines[1].split(":")[1]
            # change status of ack received to true
            ack_rcv[receiver] = True

        # updates client table when receives update message
        if header == 'update':
            table_str = lines[1].split(":", 1)[1]
            server_table = json.loads(table_str)

            client_update(server_table, clients)

            print(">>> [Client table updated.]")

        # handles when receiving create group success ack from server
        if header == 'create_group':
            ack_server = True
            group_name = lines[1].split(":", 1)[1]
            create_success = lines[2].split(":", 1)[1]

            if create_success == "True":
                print(f">>> [Group {group_name} created by Server.]")
                continue
            else:
                print(f">>> [Group {group_name} already exists.]")
                continue

        # handles when receiving list group success ack from server
        if header == 'list_groups':
            ack_server = True
            cur_groups = lines[1].split(":", 1)[1]
            cur_groups = json.loads(cur_groups)

            if len(cur_groups) == 0:
                print(">>> [No available group chats.]")
            else:
                print(">>> [Available group chats:]")

                for group in cur_groups.keys():
                    print(f">>> {group}\n")

        # handles when receiving list members success ack from server
        if header == 'list_members':
            ack_server = True
            members = lines[1].split(":", 1)[1]
            group = lines[2].split(":", 1)[1]
            members = members.split()

            print(f">>> ({group}) [Members in ]the group {group}:]")

            for member in members:
                print(f">>> ({group}) {member}")

        # handles when receiving join group success ack from server
        if header == 'join_group':
            ack_server = True
            group = lines[2].split(":", 1)[1]
            join_success = lines[3].split(":", 1)[1]

            if join_success == "True":
                cur_group.append(group)
                print(f">>> [Entered group {group} successfully]")
                continue
            else:
                print(f">>> [Group {group} does not exist]")
                continue

        # handles when receiving leave group success ack from server
        if header == 'leave_group':
            ack_server = True
            group = lines[2].split(":", 1)[1]

            print(f">>> [Leave group chat {group}]")

        # ack from server to sender in the group
        if header == "send_group":
            ack_server = True

        if header == "group_msg":
            # received server's broadcast group message
            # display the message and sends back ack to server
            sender = lines[1].split(":", 1)[1]
            user = lines[2].split(":", 1)[1]
            group = lines[3].split(":", 1)[1]
            message = lines[4].split(":", 1)[1]

            print(f">>> ({group}) Group_Message {sender}: {message}.")

            ack_to_server = "header:group_ack\n" + \
                            f"user:{user}\n" + \
                            f"group_name:{group}\n"
            client_socket.sendto(ack_to_server.encode(), (server_ip, server_port))


def serverMode(port):
    """
    The function initiates server's process.

    It kept listening from clients until closing down the terminal.
    While listening, the server behaves accordingly to the header given.

    :param port: server port number
    :return: None
    """
    global ack_group
    reg_clients = {}
    groups = {}

    # Specify: IPv4, UDP
    server_socket = socket(AF_INET, SOCK_DGRAM)
    server_socket.bind(('', port))
    print(">>> Server is online")

    while True:
        buffer, client_address = server_socket.recvfrom(4096)
        buffer = buffer.decode()
        lines = buffer.splitlines()
        header = lines[0].split(":")[1]

        # updates reg_clients table with newly registered client
        if header == 'reg':
            # assume no duplicate usernames
            user = lines[1].split(":")[1]
            ip = client_address[0]
            port = int(lines[2].split(":")[1])

            reg_msg = f"header:reg\n"
            if user in reg_clients:
                # if same IP, same port number, same username, then the user came back online.
                # if same username, different IP OR port number, then useranme already registered
                reg_ip = reg_clients[user][0]
                reg_port = reg_clients[user][1]

                if reg_ip != ip or reg_port != port:
                    reg_msg = reg_msg + f"success:False"
                    print(">>> Username already registered.")
                else:
                    reg_clients[user] = [ip, port, True, "Normal"]
                    reg_msg = reg_msg + f"success:True"
                    print(">>> Server table updated.")
            else:
                reg_clients[user] = [ip, port, True, "Normal"]
                reg_msg = reg_msg + f"success:True"
                print(">>> Server table updated.")

            # sends a msg to client to indicate successful registration
            server_socket.sendto(reg_msg.encode(), (ip, port))

            # broadcast the complete table of active reg_clients to all active reg_clients
            update_msg = dict_to_str_with_msg(reg_clients, 'update')

            # broadcast the table to all online users
            broadcast(server_socket, reg_clients, update_msg)

        # de-registers client when receive de-reg request
        if header == 'dereg':
            user = lines[1].split(":")[1]
            ip = reg_clients[user][0]
            port = reg_clients[user][1]

            # sends an ack to client
            ack_msg = f"header:dereg\n" + f"msg:{user}\n"
            serverRespond(ack_msg, server_socket, ip, port)

            # updates table: change status to offline
            reg_clients[user][2] = False
            print(">>> Server table updated.")
            update_msg = dict_to_str_with_msg(reg_clients, 'update')

            # broadcast the table to all online users
            broadcast(server_socket, reg_clients, update_msg)

        # update server table when notified by client
        if header == 'update':
            user_to_update = lines[1].split(":")[1]
            reg_clients[user_to_update][2] = not reg_clients[user_to_update][2]
            print(reg_clients)
            print("Server table updated.")

        # creates group chat when receives request from client
        if header == 'create_group':
            group_name = lines[1].split(":")[1]
            user = lines[2].split(":")[1]

            ip = reg_clients[user][0]
            port = reg_clients[user][1]

            # server check if such group exists
            group_exist = True if group_name in groups.keys() else False

            if not group_exist:
                groups[group_name] = []
                print(f">>> [Client {user} created group {group_name} successfully]")
            else:
                print(f">>> [Client {user} creating group {group_name} failed, group already exists]")

            create_success = not group_exist

            # then sends back an ack to client, client then behaves correspondingly
            ack_msg = "header:create_group\n" + \
                      f"group_name:{group_name}\n" + \
                      f"create_success:{create_success}"
            server_socket.sendto(ack_msg.encode(), (ip, port))

        if header == 'list_groups':
            user = lines[1].split(":")[1]

            ip = reg_clients[user][0]
            port = reg_clients[user][1]

            # server sends a message that includes all groups
            msg = dict_to_str_with_msg(groups, 'list_groups')

            serverRespond(msg, server_socket, ip, port)

            if len(groups) == 0:
                print(">>> [No available groups.]")
            else:
                print(f">>> [Client {user} requested listing groups, current groups:]")

                for group in groups.keys():
                    print(f">>> {group}\n")

        if header == 'list_members':
            user = lines[1].split(":")[1]
            group = lines[2].split(":")[1]

            ip = reg_clients[user][0]
            port = reg_clients[user][1]

            cur_members = groups[group]
            str_members = " ".join(cur_members)

            msg = f"header:list_members\n" + \
                  f"members:{str_members}\n" + \
                  f"group:{group}"

            serverRespond(msg, server_socket, ip, port)

            print(f">>> Client {user} requested listing members of group {group}:")

            for cur_user in cur_members:
                print(f">>> {cur_user}")

        if header == 'join_group':
            user = lines[1].split(":")[1]
            group = lines[2].split(":")[1]

            ip = reg_clients[user][0]
            port = reg_clients[user][1]

            # verify if the group exists
            group_exist = True if group in groups.keys() else False

            if group_exist:
                # let client join the group
                groups[group].append(user)
                print(f">>> [Client {user} joined group {group}]")

                reg_clients[user][3] = "Group"

                # broadcast the complete table of active reg_clients to all active reg_clients
                update_msg = dict_to_str_with_msg(reg_clients, 'update')

                # broadcast the table to all online users
                broadcast(server_socket, reg_clients, update_msg)
            else:
                print(f">>> [Client {user} joining group {group} failed, group does not exist]")

            join_success = group_exist

            # then sends an ack to user, indicating whether joining is successful
            ack_msg = "header:join_group\n" + \
                      f"user:{user}\n" + \
                      f"group_name:{group}\n" + \
                      f"join_success:{join_success}"
            server_socket.sendto(ack_msg.encode(), (ip, port))

        if header == 'leave_group':
            user = lines[1].split(":")[1]
            group = lines[2].split(":")[1]

            ip = reg_clients[user][0]
            port = reg_clients[user][1]

            # remove client from the group
            groups[group].remove(user)
            print(f">>> [Client {user} left group {group}]")

            reg_clients[user][3] = "Normal"

            print(f">>> Updated current groups: {groups}")

            # broadcast the complete table of active reg_clients to all active reg_clients
            update_msg = dict_to_str_with_msg(reg_clients, 'update')

            # broadcast the table to all online users
            broadcast(server_socket, reg_clients, update_msg)

            # then sends an ack to user, indicating whether leaving is successful
            ack_msg = "header:leave_group\n" + \
                      f"user:{user}\n" + \
                      f"group_name:{group}\n"
            server_socket.sendto(ack_msg.encode(), (ip, port))

        # when receives client's ack during group chat mode (received message)
        if header == 'group_ack':
            user = lines[1].split(":")[1]
            ack_group[user] = 1

        if header == 'send_group':
            # header, # sender # group # message
            sender_client = lines[1].split(":")[1]
            group = lines[2].split(":")[1]
            message = lines[3].split(":")[1]

            ip = reg_clients[sender_client][0]
            port = reg_clients[sender_client][1]

            print(f">>> [Client {sender_client} sent group message: {message}]")

            # sends an ack back to the sender client,
            ack_to_sender = "header:send_group\n" + \
                            f"user:{sender_client}\n" + \
                            f"group_name:{group}\n"
            server_socket.sendto(ack_to_sender.encode(), (ip, port))

            # broadcast the message to all other clients in the group chat except sender
            broadcast_users = [client for client in groups[group] if client != sender_client]

            for receiver in broadcast_users:
                msg_to_group = "header:group_msg\n" + \
                               f"user:{sender_client}\n" + \
                               f"receiver:{receiver}\n" + \
                               f"group_name:{group}\n" + \
                               f"message:{message}"
                ack_group[receiver] = 0
                cur_user_ip = reg_clients[receiver][0]
                cur_user_port = reg_clients[receiver][1]
                server_socket.sendto(msg_to_group.encode(), (cur_user_ip, cur_user_port))

            # once broadcasted, server needs another thread to count total acks received
            # from group members within 500 msecs
            count_acks = threading.Thread(target=count_recv_acks, args=(server_socket, reg_clients,
                                                                        groups, group, broadcast_users))
            count_acks.start()


def count_recv_acks(server_socket, reg_clients, groups, group, broadcast_users):
    """
    The function listens from all the broadcasted group chat users acks on another thread.

    After 500 msecs, the server removes inactive user from the group chat,
    change its' mode to normal, sends an update message to all the registered
    clients to inform updates.

    :param server_socket: server socket
    :param reg_clients: registered clients dictionary on server
    :param groups: server side dictionary that tracks all groups and members within
    :param group: string, group name
    :param broadcast_users: list of broadcasted users
    :return: None
    """
    global ack_group
    time.sleep(0.5)

    for user in broadcast_users:
        if ack_group[user] == 0:
            groups[group].remove(user)
            # on client interface, the non-responsive user should also exit group mode
            reg_clients[user][3] = "Normal"

            # broadcast the complete table of active reg_clients to all active reg_clients
            update_msg = dict_to_str_with_msg(reg_clients, 'update')

            # broadcast the table to all online users
            broadcast(server_socket, reg_clients, update_msg)
            print(f">>> [Client {user} not responsive, removed from group {group}]")
        else:
            # resets users back to 0 for future use
            ack_group[user] = 0


def clientMode(user_name, server_ip, server_port, client_port):
    """
        The function serves as client mode that waits for user's input
        on main thread to send out message headers and initiates
        client listening mode on a new thread.

        While listening, the function checks whether client is in
        normal/group chat mode, and directs to corresponding input
        mode.

        It also checks validity of user input, and prints error message
        whenever violated.

        :param user_name: client's user name to register
        :param server_ip: server IP address
        :param server_port: server port number
        :param client_port: client port number
        :return: None
        """
    global reg_success
    global dereg_ack_received
    global ack_server
    global ack_rcv
    # cur_group keeps track of client's currently attended group
    # if the list is empty, then client is in normal mode
    global cur_group

    clients = {}
    normal_mode_commands = ["send", "dereg", "create_group", "list_groups", "join_group"]
    group_mode_commands = ["send_group", "list_members", "leave_group", "dereg"]
    msg_queue = []
    client_socket = socket(AF_INET, SOCK_DGRAM)
    # error raised when timeout
    client_socket.settimeout(0.5)
    client_socket.bind(('', client_port))

    # client sends registration request to server when it came online
    reg_msg = f"header:{'reg'}\n" + \
              f"username:{user_name}\n" + \
              f"client port:{client_port}"
    client_socket.sendto(reg_msg.encode(), (server_ip, server_port))

    # initiates stop event to handle de-registration
    # and other non-responsive scenarios to stop listening thread
    stop_event = threading.Event()

    # distribute an extra thread for client to listen while active
    listen = threading.Thread(target=clientListen, args=(client_socket, clients, stop_event, msg_queue))
    listen.start()

    time.sleep(0.5)

    if ack_server:
        ack_server = False
        if reg_success:
            pass
        else:
            # other user already registered
            stop_event.set()
            listen.join()
            sys.exit()
    else:
        print(f">>> [Server not responding]")
        print(f">>> [Exiting]")
        stop_event.set()
        listen.join()
        sys.exit()

    while True:
        # handle edge case: before registration
        if len(clients) == 0:
            continue

        # check if kicked out of group by server
        if clients[user_name][3] == 'Normal':
            cur_group = []

        # use currently added group to determine whether in group chat or normal mode
        # enters normal mode
        if len(cur_group) == 0:
            # clears buffer from msg_queue
            size = len(msg_queue)

            for i in range(size):
                print(msg_queue.pop(0))

            print(">>> ", end="")
            temp = input()
            input_list = temp.split()

            try:
                header = input_list[0]
            except:
                print(">>> Invalid input, try again")
                continue

            if header not in normal_mode_commands:
                print(">>> Invalid input, try again")
                continue

            # header tells you what specific operation to do
            if header == "send":
                try:
                    recv_user = input_list[1]
                except:
                    print(">>> Invalid input, try again")
                    continue

                # If user is not registered, notify the sender
                if recv_user not in clients:
                    print(">>> Sorry, the designated user is not registered.")
                    continue

                if not clients[recv_user][2]:
                    print(">>> Sorry, the designated user is not available now.")
                    continue

                recv_ip = clients[recv_user][0]
                recv_port = clients[recv_user][1]

                message = ""
                for i in range(2, len(input_list)):
                    message = message + input_list[i] + " "
                message = message.strip()

                send_msg = "header:send\n" + \
                           f"sender:{user_name}\n" + \
                           f"receiver:{recv_user}\n" + \
                           f"IP:{recv_ip}\n" + \
                           f"port:{recv_port}\n" + \
                           f"message:{message}"

                client_socket.sendto(send_msg.encode(), (recv_ip, recv_port))

                time.sleep(0.5)
                if ack_rcv[recv_user]:
                    print(f">>> [Message received by {recv_user}.]")
                    # change ack from message receiver to False for recycling use
                    ack_rcv[recv_user] = False
                else:
                    print(f">>> [No ack from {recv_user}, message not delivered]")
                    # update local table
                    clients[recv_user][2] = False
                    # print(clients)
                    # notify the server to change recv user to offline
                    notify_msg = f"header:update\n" + \
                                 f"user:{recv_user}"
                    client_socket.sendto(notify_msg.encode(), (server_ip, server_port))

            if header == 'dereg':
                # send dereg request msg to server
                try:
                    dereg_user = input_list[1]
                except:
                    print(">>> Invalid input, try again")
                    continue

                if dereg_user != user_name:
                    print(">>> Sorry, you can't de-register any other user.")
                    continue

                dereg_msg = f"header:{'dereg'}\n" + f"msg:{dereg_user}\n"
                client_socket.sendto(dereg_msg.encode(), (server_ip, server_port))

                # Wait for client listener to change dereg ack flag to true if received
                time.sleep(0.5)

                # wait for server's ack
                if dereg_ack_received:
                    print(">>> [You are Offline. Bye.]")
                    break
                else:
                    attempts = 5
                    for i in range(attempts):
                        client_socket.sendto(dereg_msg.encode(), (server_ip, server_port))
                        print(f">>> {i + 1} time retrying...")
                        time.sleep(0.5)
                        if dereg_ack_received:
                            print(">>> You are Offline. Bye.")
                            break
                    stop_event.set()
                    listen.join()
                    print(f">>> [Server not responding]")
                    print(f">>> [Exiting]")
                    break

            if header == 'create_group':
                try:
                    group_name = input_list[1]
                except:
                    print(">>> Invalid input, try again")
                    continue

                # send a message to server
                create_req_msg = f"header:create_group\n" + \
                                 f"group_name:{group_name}\n" + \
                                 f"user:{user_name}"
                client_socket.sendto(create_req_msg.encode(), (server_ip, server_port))

                # wait for server's ack within 500 msecs
                time.sleep(0.5)

                successful = wait_and_retry(client_socket, create_req_msg, stop_event,
                                            server_ip, server_port, listen)
                if successful:
                    continue
                else:
                    break

            if header == 'list_groups':
                list_req_msg = f"header:list_groups\n" + \
                               f"user:{user_name}"
                client_socket.sendto(list_req_msg.encode(), (server_ip, server_port))

                # wait for server's ack within 500 msecs
                time.sleep(0.5)

                successful = wait_and_retry(client_socket, list_req_msg, stop_event,
                                            server_ip, server_port, listen)
                if successful:
                    continue
                else:
                    break

            if header == 'join_group':
                try:
                    group_name = input_list[1]
                except:
                    print(">>> Invalid input, try again")
                    continue

                join_req_msg = f"header:join_group\n" + \
                               f"user:{user_name}\n" + \
                               f"group:{group_name}"

                client_socket.sendto(join_req_msg.encode(), (server_ip, server_port))

                # wait for server's ack within 500 msecs
                time.sleep(0.5)

                successful = wait_and_retry(client_socket, join_req_msg, stop_event,
                                            server_ip, server_port, listen)
                if successful:
                    continue
                else:
                    break
        else:
            print(f">>> ({cur_group[0]}) ", end="")
            temp = input()
            input_list = temp.split()

            try:
                header = input_list[0]
            except:
                print(">>> Invalid input, try again")
                continue

            if header not in group_mode_commands:
                print(">>> Invalid input, try again")
                continue

            if header == 'dereg':
                # send dereg request msg to server
                try:
                    dereg_user = input_list[1]
                except:
                    print(">>> Invalid input, try again")
                    continue

                if dereg_user != user_name:
                    print(">>> Sorry, you can't de-register any other user.")
                    continue

                dereg_msg = f"header:{'dereg'}\n" + f"msg:{dereg_user}\n"
                client_socket.sendto(dereg_msg.encode(), (server_ip, server_port))

                # Wait for client listener to change dereg ack flag to true if received
                time.sleep(0.5)

                # wait for server's ack
                if dereg_ack_received:
                    print(">>> You are Offline. Bye.")
                    break
                else:
                    attempts = 5
                    for i in range(attempts):
                        client_socket.sendto(dereg_msg.encode(), (server_ip, server_port))
                        print(f">>> {i + 1} time retrying...")
                        time.sleep(0.5)
                        if dereg_ack_received:
                            print(">>> You are Offline. Bye.")
                            break
                    stop_event.set()
                    listen.join()
                    print(f">>> [Server not responding]")
                    print(f">>> [Exiting]")
                    break

            if header == 'leave_group':
                leave_req_msg = f"header:leave_group\n" + \
                                f"user:{user_name}\n" + \
                                f"group:{cur_group[0]}"

                client_socket.sendto(leave_req_msg.encode(), (server_ip, server_port))

                # wait for server's ack within 500 msecs
                time.sleep(0.5)

                if ack_server:
                    cur_group.clear()
                    ack_server = False
                    continue
                else:
                    attempts = 5
                    for i in range(attempts):
                        client_socket.sendto(leave_req_msg.encode(), (server_ip, server_port))
                        print(f">>> {i + 1} time retrying...")
                        time.sleep(0.5)
                        if ack_server:
                            cur_group.clear()
                            ack_server = False
                            continue
                    stop_event.set()
                    listen.join()
                    print(f">>> [Server not responding]")
                    print(f">>> [Exiting]")
                    break

            if header == 'send_group':
                message = ""
                for i in range(1, len(input_list)):
                    message = message + input_list[i] + " "
                message = message.strip()

                send_group_msg = "header:send_group\n" + \
                                 f"sender:{user_name}\n" + \
                                 f"group:{cur_group[0]}\n" + \
                                 f"message:{message}"

                client_socket.sendto(send_group_msg.encode(), (server_ip, server_port))
                print(f">>> Group Message sent to server.")

                time.sleep(0.5)

                # wait for server's ack
                if ack_server:
                    print(f">>> ({cur_group[0]}) [Message received by Server.]")
                    ack_server = False
                    continue
                else:
                    attempts = 5
                    for i in range(attempts):
                        client_socket.sendto(send_group_msg.encode(), (server_ip, server_port))
                        print(f">>> {i + 1} time retrying...")
                        time.sleep(0.5)
                        if ack_server:
                            print(f">>> ({cur_group[0]}) Message received by Server.")
                            ack_server = False
                            continue
                    stop_event.set()
                    listen.join()
                    print(f">>> [Server not responding]")
                    print(f">>> [Exiting]")
                    break

            if header == 'list_members':
                # send to server to list group members
                list_member_msg = f"header:list_members\n" + \
                                  f"user:{user_name}\n" + \
                                  f"group:{cur_group[0]}"

                client_socket.sendto(list_member_msg.encode(), (server_ip, server_port))

                # wait for server's ack within 500 msecs
                time.sleep(0.5)

                successful = wait_and_retry(client_socket, list_member_msg, stop_event,
                                            server_ip, server_port, listen)
                if successful:
                    continue
                else:
                    break

def wait_and_retry(client_socket, msg, stop_event, server_ip, server_port, listen):
    """
    This function is used repeatedly in client mode to retry 5 additional times
    if ack is not received from server within 500 msecs, and exits if all 5 times
    failed.

    :param client_socket: client socket to send message
    :param msg: string, message to send
    :param stop_event: stop event to kill listening thread
    :param server_ip: server's IP address
    :param server_port: server's listening port number
    :param listen: listening thread on client mode
    :return: None
    """
    global ack_server
    if ack_server:
        ack_server = False
        return True
    else:
        attempts = 5
        for i in range(attempts):
            client_socket.sendto(msg.encode(), (server_ip, server_port))
            print(f">>> {i + 1} time retrying...")
            time.sleep(0.5)
            if ack_server:
                ack_server = False
                return True
        stop_event.set()
        listen.join()
        print(f">>> [Server not responding]")
        print(f">>> [Exiting]")
        return False


def is_valid_port(port):
    """
    The function returns True if given port is valid (within range [1024, 65535]).
    If either not within range or invalid type, print error message and returns False.

    :param port: port number
    :return: boolean: indicates validity
    """
    try:
        # Try to convert the port number to an integer
        port_int = int(port)
        # Check if the port number is within the valid range
        if port_int < 1024 or port_int > 65535:
            print("Port number should be within [1024, 65535], please try again.")
            return False
    except ValueError:
        # If the conversion to an integer fails, the port number is invalid
        print("Invalid port number type, please try again.")
        return False

    return port_int


def is_valid_ip(ip):
    """
    The function returns the IP address if it's valid. Otherwise, returns False.

    :param ip: input IP address
    :return: IP or False
    """
    if ip == 'localhost':
        return ip
    try:
        # Try to create a socket with the given IP address
        socket.inet_aton(ip)
    except:
        # If the socket creation fails, the IP address is invalid
        print("Invalid IP address, please try again.")
        return False
    return ip


if __name__ == '__main__':
    mode = sys.argv[1]

    if mode == '-s':
        # input port number check
        server_port = is_valid_port(sys.argv[2])
        # only initiates the server if port number is valid
        if server_port:
            serverMode(server_port)

    elif mode == '-c':
        user_name = sys.argv[2]
        server_ip = is_valid_ip(sys.argv[3])
        server_port = is_valid_port(sys.argv[4])
        client_port = is_valid_port(sys.argv[5])

        # only initiates client connection if both IP address and port numbers are valid
        if server_ip != False and server_port != False and client_port != False:
            clientMode(user_name, server_ip, server_port, client_port)
