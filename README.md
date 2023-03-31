Name: Zimu An

UNI: za2323

# CSEEW4119 Computer Networks: Chat Application

This computer network project is a simple chat application implemented using Python socket programming via UDP. The application involves one server and multiple clients, where clients in `normal` mode can register/de-register, send private messages directly to each other, create group chat, list existing group chats, and join any group chat. If messages are sent to clients in `group` mode, the receiver side uses a queue to buffer them, and displays until changed back to `normal` mode. By joining one group chat the client enters `group` mode, which allows client to send group messages within the group, list group members, leave the group if the client wants to, or de-register. Clients online status and group mode are constantly monitored, and server will broadcast the update to other clients once changes are observed.

## Start the application

In order to start the program, one must initiate server process first by using the following line of code with a destined port number in range [1024, 65535].
```http
  python3 ChatApp.py -s port_number
```

Any number of clients should be able to connect/register to the server using the following code. One must clarify the username, server_ip, server_port, and client_port. If username already exists, server checks if IP and port number is the same as the existing one, if so, it means that the offline user came back online. If not, another user is trying to register using the same name. The server rejects.
```http
  python3 ChatApp.py -c username server_ip server_port client_port
```

In both server/client initate process, the program checks if IP and port numbers given are valid, and prints corresponding error message.

## Client APIs

Most of the operations below uses stop-and-wait mechanism where client would wait for 500 msec once the request is sent, and check if intended target (could be either server or client depending on the operation) receives it. Successful response would mean that the receiver sends back an ack, and program proceeds. Otherwise, the client would report offline status of client on the other side to server, or exit if server is not responsive.

### Normal Mode

#### Send private DM to client
```
  send other_user message
```

#### Create a group chat

```
  create_group group_name
```

#### List all available group chat names

```
  list_groups
```

#### Join a group chat (enter group chat mode)

```
  join_group group_name
```

### Group Mode
#### Send group message within current group

```
  send_group message
```

#### List all members in current group

```
  list_members
```

#### Leave group chat (back to normal mode)

```
  leave_group
```

### Both Modes
#### De-register from server

```
  Dereg user_name
```

If the client attempt to input empty command, or exclusive command in noraml/group mode while the client is already in group/normal mode, or any other invalid commands, the program will print invalid input to notify the user. 

## Data Structure Used
This program is function oriented instead of object oriented, so no class is created.
Instead, I used global variables as flags to record different reply status and functions to help interact between clients, and server.

### Server Side
#### variables
```global ack_group```: a dictionary where key is username, value is either 0 or 1. This is used by the server to count number of acks received from client when broadcasting messages within a group.

```reg_clients```: a dictionary maintained by server, where key is user_name, value is a list of 4 elements [IP, port_num, online_status(True or False), group_mode(Normal or Group)]. It's used to record dynamic status of users.

```groups```: a dictionary where key is group_name, value is a list of user names. This is used to maintain which users are in which group, add and remove users when necessary.

```server_socket```: server socket that kept listening to client requests and send acks and responses to clients. 

### Client Side
####  variables
```global reg_success```: a boolean which initialized as False, to indicate whether registration is successful. The client listening mode modifies this according to server's message.

```global dereg_ack_received```:a boolean which initialized as False, to indicate whether deregistration ack is received. The client listening mode modifies this according to server's message. The main thread then either exits (ack_received) or retry 5 times (as the scope indicates).

```global ack_rcv```: a dictionary where key is user_name, value is a boolean. [user_name, True] indicates that the current client receives the ack from ```user_name```, and performs accordingly.

```global cur_group```: a list of size at most 1 that indicates which group the client joined. If the list is empty, then client is in Normal mode.

```global ack_server```: a boolean which initialized as False, to indicate whether server replied an ack. On client listening thread, it changes the flag to True if received an ack from server, and will reverse to False on main thread after checking for future use.

```clients```: a dictionary similar to reg_clients maintained, with the same schema. The table will update once received an update notification by server.

```normal_mode_commands```: a list of valid noraml mode commands. If further new commands are developed, they should be added in this list.

```group_mode_commands```: a list of valid group mode commands. If further new commands are developed, they should be added in this list.

```msg_queue```: a queue which buffers private messages received when the client is in group mode. While a sender tries to add a message to this queue, locking mechanism is implemented. The lock is released once the operation is finished.

```client_socket```: client socket to send requests to server and other clients. It's also listening via multi-threading.

```stop_event```: a threading stop-event used to stop listening thread.

```listen```: a new thread used for client socket to listen while also taking user inputs.

### Helper Functions
```dict_to_str_with_msg```: the function casts the given dictionary to a string for
    (usually server) to pass over through a message.

```client_update```: the function receives server table from server and updates
    new registerd clients, online status, and group/normal mode
    on client side table.

```broadcast```: the function uses server_socket to broadcast given msg
    to all online clients given in the dictionary clients.

```serverRespond```: the function simply sends a response (msg) from server to the
    client given its' (IP, port) through server socket.

```count_recv_acks```: the function listens from all the broadcasted group chat users acks on another thread.

    After 500 msecs, the server removes inactive user from the group chat,
    change its' mode to normal, sends an update message to all the registered
    clients to inform updates.

```wait_and_retry```: this function is used repeatedly in client mode to retry 5 additional times
    if ack is not received from server within 500 msecs, and exits if all 5 times
    failed.

```is_valid_port```: the function returns True if given port is valid (within range [1024, 65535]).
    If either not within range or invalid type, print error message and returns False.

```is_valid_ip```: the function returns the IP address if it's valid. Otherwise, returns False.

## Bugs and Future Improvements
Currently, this application can perform all required functionality. However, one noticeable caveat is in the terminal. When printing messages, the delay and wait may overlap default waiting mode ">>>" with some other print statements such as ">>> Welcome, you are registered." which results in ">>>>>> Welcome...", which makes the display less pleasing, but won't affect any functionality.

If time allows, another improvement might be changing it to object oriented. Many global variables and functions might make it less readable and harder to maintain. Better decoupling might also help with maintenance.

Furthermore, since the application is implemented in a stop-and-wait fashion, it implies non-optimal scalability. Even though it functions properly on a small scale of users, once the user base increase exponentially, efficiency would degrade as well as user experience. 