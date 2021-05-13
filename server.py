"""
AUTHORS: Antoine Andrieux & Thibaut Colson & Amine Djuric
COURSE: LINGI2145 (INFO-Y118) Mobile and embedded computing
DATE: 11/05/2021
"""

import sys
import re
from threading import Thread
import socket
from functools import partial


UDP_IP = "bbbb::1"  # = 0.0.0.0 u IPv4
UDP_SERVER_PORT = 5678
UDP_CLIENT_PORT = 8765

MAX_NBR_SENSOR_VALUES = 10
REGEX_IPV6 = "(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
COMMAND_INSTRUCTIONS = \
    "\n=================== Server IoTs Simulation ===================\n\n\
Command:\n\
    ------------- Server -------------\n\
  - help :                                show help page\n\
  - exit :                                shutdown the server\n\n\
  - show motes :                          show motes connected to the server\n\n\
  - verbose/<on|off> :                    <show|hide> received data from IoTs devices (motes) (default: off)\n\
  - stop :                                hide received data from IoTs devices (motes)\n\
    ----------------------------------\n\n\
    ------------ Mote LED ------------\n\
  - led/<led_ip_address>/\n\
    <red|green|blue>/<on|off> :           turn <on|off> <red|green|blue> led (default: off)\n\
                                          (Example: led/bbbb::c30c:0:0:2/red/on)\n\
    ----------------------------------\n\n\
    ------------ Automation ----------\n\
  - automate sensor_activity/\n\
    <sensor_ip_address>/led/\n\
    <led_ip_address>/<red|green|blue>/\n\
    <on|off> :                            turn <on|off> <red|green|blue> led when there is an activity on the sensor (default: off)\n\
                                          (Example: automate sensor_activity/bbbb::c30c:0:0:1/led/bbbb::c30c:0:0:2/red/on)\n\
  - automate sensor_temperature/\n\
    <sensor_ip_address>/valve/\n\
    <valve_ip_address>/<number|off> :     change temperature on the temperature valve according to the temperature sensor (default: off)\n\
                                          (Example: automate sensor_temperature/bbbb::c30c:0:0:1/valve/bbbb::c30c:0:0:2/40)\n\n\
==============================================================\n"
MESSAGE_INPUT = "\nType a command (for help, type: help) : "


class Server:
    def __init__(self):
        """ Constructor """
        self.nodes = {}

        self.sock = socket.socket(socket.AF_INET6,    # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.sock.bind((UDP_IP, UDP_SERVER_PORT))

    def send_data(self, address, data):
        """Request sending to the border router"""
        self.sock.sendto(data.encode(), (address, UDP_CLIENT_PORT))

    def update_node(self, node, value):
        """Update the sensor value list of a node with the last data or add a new node in the list of nodes"""
        if node in self.nodes:
            if len(self.nodes[node]) >= MAX_NBR_SENSOR_VALUES:
                self.nodes[node].pop(0)
            self.nodes[node].append(value)
        else:   # If node is unknown by the server
            self.nodes[node] = [value]

    def receive_data(self):
        print("Server listening on port " + str(UDP_SERVER_PORT) + "...\n")

        while True:
            data, addr = self.sock.recvfrom(1024)  # buffer size is 1024 bytes
            # if(re.match("^\d{1,2}/\d{1,2}$", data) is None):
            #     print("Wrong format")
            self.update_node(addr[0], data)
            if verbose:
                print(str(addr[0]) + " : " +
                      str(data) + " (stop verbose? stop)")
            # self.process_node(node)

    def extract_fields_from_command(self, command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state):
        try:
            mote_dest_ip_addr = re.search('led/(.+?)/', command).group(1)
            command = command.replace(mote_dest_ip_addr, '<led_ip_address>')
            led_color = re.search(
                'led/<led_ip_address>/(.+?)/', command).group(1)
            command = command.replace(led_color, '<red|green|blue>')
            led_state = command.split(
                'led/<led_ip_address>/<red|green|blue>/')[-1]
            command = command.replace(led_state, '<on|off>')
            # Inputs validation
            if not re.match(REGEX_IPV6, mote_dest_ip_addr) or led_color not in ["red", "green", "blue"] or led_state not in ["on", "off"]:
                command = ""
        except AttributeError:
            None

        try:
            # Activity sensor
            mote_src_ip_addr = re.search(
                'automate sensor_activity/(.+?)/', command).group(1)
            command = command.replace(mote_src_ip_addr, '<sensor_ip_address>')
            # Inputs validation
            if not re.match(REGEX_IPV6, mote_src_ip_addr):
                command = ""
        except AttributeError:
            # Temperature sensor
            try:
                mote_src_ip_addr = re.search(
                    'automate sensor_temperature/(.+?)/', command).group(1)
                command = command.replace(
                    mote_src_ip_addr, '<sensor_ip_address>')
                mote_dest_ip_addr = re.search('valve/(.+?)/', command).group(1)
                command = command.replace(
                    mote_dest_ip_addr, '<valve_ip_address>')
                valve_state = command.split(
                    'valve/<valve_ip_address>/')[-1]
                command = command.replace(valve_state, '<number|off>')
                # Inputs validation
                if not re.match(REGEX_IPV6, mote_src_ip_addr) or not re.match(REGEX_IPV6, mote_dest_ip_addr) or (valve_state != "off" and (not valve_state.isdigit() or (valve_state.isdigit() and not (int(valve_state) <= 100 and int(valve_state) >= 0)))):
                    command = ""
            except AttributeError:
                None

        return command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state

    def cmd_print_help(self):
        print(COMMAND_INSTRUCTIONS)

    def cmd_toogle_verbose(self, bool):
        global verbose
        verbose = bool

    def cmd_show_motes(self):
        for n in self.nodes:
            print(str(n) + " : " + str(self.nodes[n]))

    def cmd_toggle_rgb_led(self, mote_dest_ip_addr, led_color, led_state):
        data = led_color + "/" + led_state
        self.send_data(mote_dest_ip_addr, data)
        print('Command sent! Led ' + data)

    def cmd_automate_activity_led(self, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state):
        print(mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state)

    def cmd_automate_temperature_led(self, mote_src_ip_addr, mote_dest_ip_addr, valve_state):
        print(mote_src_ip_addr, mote_dest_ip_addr, valve_state)

    def cmd_exit(self):
        sys.exit()

    def cmd_invalid(self):
        print("Invalid command. Try again.")

    def run(self):
        global verbose
        verbose = False
        command = None
        mote_dest_ip_addr = mote_src_ip_addr = led_color = led_state = valve_state = None

        self.cmd_print_help()

        recv_process = Thread(target=self.receive_data)
        recv_process.daemon = True
        recv_process.start()

        while True:
            command = input(MESSAGE_INPUT if command !=
                            "verbose/on" else "\n")

            command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state = self.extract_fields_from_command(
                command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state)

            switcher = {
                "help": self.cmd_print_help,
                "verbose/on": partial(self.cmd_toogle_verbose, True),
                "verbose/off": partial(self.cmd_toogle_verbose, False),
                "stop": partial(self.cmd_toogle_verbose, False),
                "show motes": self.cmd_show_motes,
                "led/<led_ip_address>/<red|green|blue>/<on|off>": partial(self.cmd_toggle_rgb_led, mote_dest_ip_addr, led_color, led_state),
                "automate sensor_activity/<sensor_ip_address>/led/<led_ip_address>/<red|green|blue>/<on|off>": partial(self.cmd_automate_activity_led, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state),
                "automate sensor_temperature/<sensor_ip_address>/valve/<valve_ip_address>/<number|off>": partial(self.cmd_automate_temperature_led, mote_src_ip_addr, mote_dest_ip_addr, valve_state),
                "exit": self.cmd_exit,
            }
            switcher.get(command, self.cmd_invalid)()


def main():
    server = Server()
    server.run()


if __name__ == "__main__":
    main()
