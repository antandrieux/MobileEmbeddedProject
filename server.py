import socket

UDP_IP = "bbbb::1"  # = 0.0.0.0 u IPv4
UDP_PORT = 5678

MAX_NBR_SENSOR_VALUES = 8


class Server:
    def __init__(self):
        """ Constructor
        """
        self.nodes = {}

        self.sock = socket.socket(socket.AF_INET6,    # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.sock.bind((UDP_IP, UDP_PORT))

    def send_data(self, address, data):
        """Request sending to the border router"""
        self.sock.sendto(data.encode(), (address, UDP_PORT))

    def update_node(self, node, value):
        """Update the sensor value list of a node with the last receipt."""
        if node in self.nodes:
            if len(self.nodes[node]) >= MAX_NBR_SENSOR_VALUES:
                self.nodes[node].pop(0)
            self.nodes[node].append(value)
        else:   # node unknown by the server
            self.nodes[node] = [value]
        for n in self.nodes:
            print(str(n) + ": " + str(self.nodes[n]))

    def run(self):
        while True:
            #data, addr = self.sock.recvfrom(1024)  # buffer size is 1024 bytes
            # print("test")
            # if(re.match("^\d{1,2}/\d{1,2}$", data) is None):
            #     print("Wrong format")
            #print("received message:", data)
            self.send_data("bbbb::c30c:0:0:2", "on/red")
            #print("data send to lamp")


def main():
    server = Server()
    server.run()


if(__name__ == "__main__"):
    main()
