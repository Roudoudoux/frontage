import socket
import sys

# host IP is static and the PORT is fixed to 8080
HOST='10.0.0.1'
PORT=8080

# socket creation
s= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('Socket created')

# connection counter
i=0

try:
	s.bind((HOST, PORT))
except socket.error as msg:
	print('Bind failed. Err code :' + str(msg[0]) + 'msg :' + msg[1])
	sys.exit()

s.listen(11)

while 1:
	print(str(i) + '...')
	i+= 1
	(conn, addr) = s.accept()
	print('Server (10.0.0.1) connected with device (' + addr[0] + ')')
	print('Connection is now listening')
	#silly loop which print anything recieve througth the connection
	while True :
		data = conn.recv(1500)
		reply = 'OK... : ' + str(data)
		print(reply)
		if not data:
			break

s.close()
