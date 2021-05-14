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
import uuid
import time


UDP_IP = "bbbb::1"  # = 0.0.0.0 u IPv4
UDP_SERVER_PORT = 5678
UDP_CLIENT_PORT = 8765

TYPES_OF_MOTE = {"1": "TEMPERATURE_DATA",
                 "2": "ACTIVITY_DATA", "3": "LED", "4": "VALVE"}
TYPES_OF_RECV_MOTE = ["LED", "VALVE"]
TYPES_OF_DATA_MOTE = ["TEMPERATURE_DATA", "ACTIVITY_DATA"]
LED_COLORS = {"red": "1", "green": "2", "blue": "3"}
MOTE_STATES = {"on": "1", "off": "0"}
ON = "1"
OFF = "0"

BUFFER_SIZE = 1024
KEEP_ALIVE_MSG = "KEEP_ALIVE"
KEEP_ALIVE_TIMEOUT = 120

REGEX_IPV6 = "(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
COMMAND_INSTRUCTIONS = \
    "\n=================== Server IoTs Simulation ===================\n\n\
Command:\n\
    ------------- Server -------------\n\
  - help :                                show help page\n\
  - exit :                                shutdown the server\n\n\
  - show motes :                          show motes connected to the server\n\
  - show automations :                    show automations configured in the server\n\n\
  - verbose/<on|off> :                    <show|hide> received data from IoTs devices (motes) (default: off)\n\
  - stop :                                hide received data from IoTs devices (motes)\n\
    ----------------------------------\n\n\
    ------------ Mote LED ------------\n\
  - led/<led_ip_address>/\n\
    <red|green|blue>/<on|off> :           turn <on|off> <red|green|blue> led (default: off)\n\
                                          (Example: led/bbbb::c30c:0:0:2/red/on)\n\
    - valve/<valve_ip_address>/\n\
    <on|off> :                            turn <on|off> a thermostatic valve (default: off)\n\
                                          (Example: valve/bbbb::c30c:0:0:2/on)\n\
    ----------------------------------\n\n\
    ------------ Automation ----------\n\
  - automate sensor_activity/\n\
    <sensor_ip_address>/led/\n\
    <led_ip_address>/<red|green|blue> :   turn on <red|green|blue> led when there is an activity on the sensor (default: off)\n\
                                          (Example: automate sensor_activity/bbbb::c30c:0:0:2/led/bbbb::c30c:0:0:4/red)\n\
  - automate sensor_temperature/\n\
    <sensor_ip_address>/valve/\n\
    <valve_ip_address>/<number> :         change temperature on the temperature valve when the temperature\n\
                                          (given by the temperature sensor) is bellow a given number (default: off)\n\
                                          <number> has to be between 0 and 100.\n\
                                          (Example: automate sensor_temperature/bbbb::c30c:0:0:3/valve/bbbb::c30c:0:0:6/50)\n\n\
  - remove automation/<ID> :              remove an automation by its ID (\"show automations\" to search IDs)\n\n\
==============================================================\n"
MESSAGE_INPUT = "\nType a command (for help, type: help) : "


class Server:
    def __init__(self):
        """ Constructor """
        self.nodes = {}
        self.automations = {}

        self.sock = socket.socket(socket.AF_INET6,    # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.sock.bind((UDP_IP, UDP_SERVER_PORT))

    def send_data(self, address, data):
        """ Request sending to the mote through the border router """
        self.sock.sendto(data.encode(), (address, UDP_CLIENT_PORT))

    def update_node(self, addr, value):
        """ Update the data of the node/mote, and check and operate any automation """
        try:
            [type_of_data, data] = value.split(",")
            type_of_data = TYPES_OF_MOTE[type_of_data]

            if not ((type_of_data in TYPES_OF_DATA_MOTE and data.isdigit())
                    or (type_of_data in TYPES_OF_RECV_MOTE and data == KEEP_ALIVE_MSG)):
                raise Exception("Wrong format message")

            if addr in self.nodes:
                if data != KEEP_ALIVE_MSG:
                    # Replace data with the new received data
                    self.nodes[addr]["data"] = data
            else:   # If node is unknown by the server
                self.nodes[addr] = {"type": type_of_data, "data": data}

            # refresh last connection status => keep alive
            self.nodes[addr]["last_connection"] = time.time()

            if verbose:
                print("Message received     => " + addr + " : " +
                      type_of_data + "," + data + " (stop verbose? stop)")

            if data != KEEP_ALIVE_MSG:
                self.check_and_automate(addr, data)

        except Exception:
            # Ignores the message when it has the wrong format
            None

    def send_automation(self, mote_src_ip_addr, mote_dest_ip_addr, type, command, command_to_display):
        self.sock.sendto(command.encode(
        ), (mote_dest_ip_addr, UDP_CLIENT_PORT))
        if verbose:
            print("Automation triggered => " + type + " (" + mote_src_ip_addr + " to " + mote_dest_ip_addr + ") => command: " +
                  command_to_display + " (stop verbose? stop)")

    def check_and_automate(self, mote_src_ip_addr, data):
        if mote_src_ip_addr in self.automations:
            # run all automations for this source mote
            for automation in self.automations[mote_src_ip_addr]:
                # Make automation only to the mote still connected to the server (KEEP_ALIVE)
                if automation["mote_dest_ip_addr"] in self.nodes:

                    # if the sensor detects an activity => activate the led in a chosen color
                    if automation["type"] == "Activity to led":
                        if data == ON:
                            self.send_automation(
                                mote_src_ip_addr, automation["mote_dest_ip_addr"], automation["type"], LED_COLORS[automation["value"]] + "/" + ON,  automation["value"] + "/on")
                        elif data == OFF:
                            self.send_automation(
                                mote_src_ip_addr, automation["mote_dest_ip_addr"], automation["type"], LED_COLORS[automation["value"]] + "/" + OFF,  automation["value"] + "/off")

                    # if the sensor gets a temperature bellow than the wanted temperature => activate the thermostatic  valve
                    elif automation["type"] == "Temperature to valve":
                        if int(data) <= int(automation["value"]):
                            command = ON
                            command_to_display = "on"
                        else:
                            command = OFF
                            command_to_display = "off"
                        self.send_automation(
                            mote_src_ip_addr, automation["mote_dest_ip_addr"], automation["type"], command, command_to_display)

    def receive_data(self):
        print("Server listening on port " + str(UDP_SERVER_PORT) + "...\n")

        while True:
            data, addr = self.sock.recvfrom(
                BUFFER_SIZE)  # buffer size is 1024 bytes
            data = data.decode("utf-8")
            self.update_node(addr[0], data)

    def extract_fields_from_command(self, command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state, automation_ID):
        try:
            # Led control
            mote_dest_ip_addr = re.search('led/(.+?)/', command).group(1)
            command = command.replace(mote_dest_ip_addr, '<led_ip_address>')
            led_color = re.search(
                'led/<led_ip_address>/(.+?)/', command).group(1)
            command = command.replace(led_color, '<red|green|blue>')
            led_state = command.split(
                'led/<led_ip_address>/<red|green|blue>/')[-1]
            command = command.replace(led_state, '<on|off>')
            # Inputs validation
            if not re.match(REGEX_IPV6, mote_dest_ip_addr) \
                    or led_color not in LED_COLORS or led_state not in MOTE_STATES:
                command = ""
        except AttributeError:
            None

        try:
            # Valve control
            mote_dest_ip_addr = re.search(
                'valve/(.+?)/', command).group(1)
            command = command.replace(
                mote_dest_ip_addr, '<valve_ip_address>')
            valve_state = command.split(
                'valve/<valve_ip_address>/')[-1]
            command = command.replace(valve_state, '<value>')
            # Inputs validation
            if not re.match(REGEX_IPV6, mote_dest_ip_addr) \
                    or (not re.search('automate sensor_temperature/(.+?)/', command)
                        and valve_state not in MOTE_STATES):
                command = ""
        except AttributeError:
            None

        try:
            # Activity sensor
            mote_src_ip_addr = re.search(
                'automate sensor_activity/(.+?)/', command).group(1)
            command = command.replace(mote_src_ip_addr, '<sensor_ip_address>')
            led_color = command.split('led/<led_ip_address>/')[-1]
            command = command.replace(led_color, '<red|green|blue>')
            # Inputs validation
            if not re.match(REGEX_IPV6, mote_src_ip_addr):
                command = ""
        except AttributeError:
            try:
                # Temperature sensor
                mote_src_ip_addr = re.search(
                    'automate sensor_temperature/(.+?)/', command).group(1)
                command = command.replace(
                    mote_src_ip_addr, '<sensor_ip_address>')
                # Inputs validation
                if not re.match(REGEX_IPV6, mote_src_ip_addr) or not valve_state.isdigit() \
                        or (valve_state.isdigit() and not (int(valve_state) <= 100 and int(valve_state) >= 0)):
                    command = ""
            except AttributeError:
                None

        if 'remove automation/' in command:
            # Remove automation
            automation_ID = command.split('remove automation/')[-1]
            command = command.replace(automation_ID, '<ID>')

        return command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state, automation_ID

    def cmd_print_help(self):
        print(COMMAND_INSTRUCTIONS)

    def cmd_toogle_verbose(self, bool):
        global verbose
        verbose = bool

    def cmd_show_motes(self):
        if len(self.nodes) == 0:
            print(
                "No motes connected... Wait until a message data comes from a mote and try again.")
        for n in self.nodes:
            print(str(n) + " : " + str(self.nodes[n]) + " (last connection: " + time.strftime(
                "%b %d %Y %H:%M:%S %Z", time.gmtime(self.nodes[n]["last_connection"])) + ")")

    def cmd_show_automations(self):
        if len(self.nodes) == 0:
            print("No automation configured... To create a new one, type \"automate sensor_temperature/<sensor_ip_address>/valve/<valve_ip_address>/<number>\"")
        for addr_automations in self.automations:
            for automation in self.automations[addr_automations]:
                print("\nID: " + automation["ID"] +
                      "\n\t- Type: " + automation["type"] +
                      "\n\t- Source mote: " + addr_automations +
                      "\n\t- Destination mote: " + automation["mote_dest_ip_addr"] +
                      "\n\t- Value: " + automation["value"] +
                      "\n-------------------------------------------------")

    def cmd_toggle_rgb_led(self, mote_dest_ip_addr, led_color, led_state):
        command = LED_COLORS[led_color] + "/" + MOTE_STATES[led_state]
        self.send_data(mote_dest_ip_addr, command)
        print('Command sent! Led ' + led_color + "/" + led_state)

    def cmd_toggle_valve(self, mote_dest_ip_addr, valve_state):
        command = MOTE_STATES[valve_state]
        self.send_data(mote_dest_ip_addr, command)
        print('Command sent! Valve ' + valve_state)

    def cmd_create_automation(self, type, mote_src_ip_addr, mote_dest_ip_addr, value):
        new_automation = {"ID": uuid.uuid4().hex, "type": type,
                          "mote_dest_ip_addr": mote_dest_ip_addr, "value": value}

        if mote_src_ip_addr in self.automations:
            self.automations[mote_src_ip_addr].append(new_automation)
        else:
            # If no automation on this source mote is set
            self.automations[mote_src_ip_addr] = [new_automation]

        self.print_new_automation(mote_src_ip_addr, new_automation)

    def cmd_remove_automation(self, automation_ID):
        for addr_automations in self.automations:
            for i in range(len(self.automations[addr_automations])):
                if self.automations[addr_automations][i]["ID"] == automation_ID:
                    self.automations[addr_automations].pop(i)
                    print("Automation removed!")
                    return

    def cmd_exit(self):
        sys.exit()

    def cmd_invalid(self):
        print("Invalid command. Try again.")

    def print_new_automation(self, mote_src_ip_addr, automation):
        print("New automation created!" +
              "\n\t- ID: " + automation["ID"] +
              "\n\t- Type: " + automation["type"] +
              "\n\t- Source mote: " + mote_src_ip_addr +
              "\n\t- Destination mote: " + automation["mote_dest_ip_addr"] +
              "\n\t- Command: " + automation["value"])

    def check_keep_alive(self):
        while True:
            time.sleep(KEEP_ALIVE_TIMEOUT)
            for n in list(self.nodes):
                if (self.nodes[n]["last_connection"] + KEEP_ALIVE_TIMEOUT) < time.time():
                    if verbose:
                        print("KEEP_ALIVE process   => No response from " + n +
                              " anymore. No automation will be triggered for this mote anymore!")
                    del self.nodes[n]

    def run(self):
        global verbose
        verbose = False
        command = None
        mote_dest_ip_addr = mote_src_ip_addr = led_color = led_state = valve_state = automation_ID = None

        self.cmd_print_help()

        recv_process = Thread(target=self.receive_data)
        recv_process.daemon = True
        recv_process.start()

        keep_alive_process = Thread(target=self.check_keep_alive)
        keep_alive_process.daemon = True
        keep_alive_process.start()

        while True:
            command = input(MESSAGE_INPUT if command !=
                            "verbose/on" else "\n")

            command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state, automation_ID = self.extract_fields_from_command(
                command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state, automation_ID)

            switcher = {
                "help": self.cmd_print_help,
                "verbose/on": partial(self.cmd_toogle_verbose, True),
                "verbose/off": partial(self.cmd_toogle_verbose, False),
                "stop": partial(self.cmd_toogle_verbose, False),
                "show motes": self.cmd_show_motes,
                "show automations": self.cmd_show_automations,
                "led/<led_ip_address>/<red|green|blue>/<on|off>": partial(self.cmd_toggle_rgb_led, mote_dest_ip_addr, led_color, led_state),
                "valve/<valve_ip_address>/<value>": partial(self.cmd_toggle_valve, mote_dest_ip_addr, valve_state),
                "automate sensor_activity/<sensor_ip_address>/led/<led_ip_address>/<red|green|blue>": partial(self.cmd_create_automation, "Activity to led", mote_src_ip_addr, mote_dest_ip_addr, led_color),
                "automate sensor_temperature/<sensor_ip_address>/valve/<valve_ip_address>/<value>": partial(self.cmd_create_automation, "Temperature to valve", mote_src_ip_addr, mote_dest_ip_addr, valve_state),
                "remove automation/<ID>": partial(self.cmd_remove_automation, automation_ID),
                "exit": self.cmd_exit,
            }
            switcher.get(command, self.cmd_invalid)()


def main():
    server = Server()
    server.run()


if __name__ == "__main__":
    main()
