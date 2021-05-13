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


UDP_IP = "bbbb::1"  # = 0.0.0.0 u IPv4
UDP_SERVER_PORT = 5678
UDP_CLIENT_PORT = 8765

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
                                          (Example: automate sensor_activity/bbbb::c30c:0:0:1/led/bbbb::c30c:0:0:2/red)\n\
  - automate sensor_temperature/\n\
    <sensor_ip_address>/valve/\n\
    <valve_ip_address>/<number> :         change temperature on the temperature valve when the temperature\n\
                                          (given by the temperature sensor) is bellow a given number (default: off)\n\
                                          <number> has to be between 0 and 100.\n\
                                          (Example: automate sensor_temperature/bbbb::c30c:0:0:1/valve/bbbb::c30c:0:0:2/40)\n\n\
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
            if type_of_data not in ["TEMPERATURE_DATA", "ACTIVITY_DATA"] or not data.isdigit():
                raise Exception("Wrong format message")

            if addr in self.nodes:
                # Replace data with the new received data
                self.nodes[addr]["data"] = data
            else:   # If node is unknown by the server
                self.nodes[addr] = {"type": type_of_data, "data": data}

            if verbose:
                print("Message received     => " + addr + " : " +
                      data + " (stop verbose? stop)")

            self.check_and_automate(addr, data)

        except Exception:
            # Ignores the message when it has the wrong format
            None

    def send_automation(self, mote_src_ip_addr, mote_dest_ip_addr, type, command):
        self.sock.sendto(command.encode(
        ), (mote_dest_ip_addr, UDP_CLIENT_PORT))
        if verbose:
            print("Automation triggered => " + type + " (" + mote_src_ip_addr + " to " + mote_dest_ip_addr + ") => command: " +
                  command + " (stop verbose? stop)")

    def check_and_automate(self, mote_src_ip_addr, data):
        if mote_src_ip_addr in self.automations:
            # run all automations for this source mote
            for automation in self.automations[mote_src_ip_addr]:

                # if the sensor detects an activity => activate the led in a chosen color
                if automation["type"] == "Activity to led":
                    if data == "1":
                        self.send_automation(
                            mote_src_ip_addr, automation["mote_dest_ip_addr"], automation["type"], automation["value"] + "/on")
                    elif data == "0":
                        self.send_automation(
                            mote_src_ip_addr, automation["mote_dest_ip_addr"], automation["type"], automation["value"] + "/off")

                # if the sensor gets a temperature bellow than the wanted temperature => activate the thermostatic  valve
                elif automation["type"] == "Temperature to valve":
                    if int(data) <= int(automation["value"]):
                        command = "valve/on"
                    else:
                        command = "valve/off"
                    self.send_automation(
                        self, mote_src_ip_addr, automation["mote_dest_ip_addr"], automation["type"], command)

    def receive_data(self):
        print("Server listening on port " + str(UDP_SERVER_PORT) + "...\n")

        while True:
            data, addr = self.sock.recvfrom(1024)  # buffer size is 1024 bytes
            data = data.decode("utf-8")
            self.update_node(addr[0], data)

    def extract_fields_from_command(self, command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state):
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
                    or led_color not in ["red", "green", "blue"] or led_state not in ["on", "off"]:
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
                        and valve_state not in ["on", "off"]):
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

        return command, mote_src_ip_addr, mote_dest_ip_addr, led_color, led_state, valve_state

    def cmd_print_help(self):
        print(COMMAND_INSTRUCTIONS)

    def cmd_toogle_verbose(self, bool):
        global verbose
        verbose = bool

    def cmd_show_motes(self):
        for n in self.nodes:
            print(str(n) + " : " + str(self.nodes[n]))

    def cmd_show_automations(self):
        for addr_automations in self.automations:
            for automation in self.automations[addr_automations]:
                print("\n\t- ID: " + automation["ID"] +
                      "\n\t- Type: " + automation["type"] +
                      "\n\t- Source mote: " + addr_automations +
                      "\n\t- Destination mote: " + automation["mote_dest_ip_addr"] +
                      "\n\t- Value: " + automation["value"] +
                      "\n-------------------------------------------------")

    def cmd_toggle_rgb_led(self, mote_dest_ip_addr, led_color, led_state):
        command = led_color + "/" + led_state
        self.send_data(mote_dest_ip_addr, command)
        print('Command sent! Led ' + command)

    def cmd_toggle_valve(self, mote_dest_ip_addr, valve_state):
        command = "valve/" + valve_state
        self.send_data(mote_dest_ip_addr, command)
        print('Command sent! Valve ' + command)

    def create_automation(self, type, mote_src_ip_addr, mote_dest_ip_addr, value):
        new_automation = {"ID": uuid.uuid4().hex, "type": type,
                          "mote_dest_ip_addr": mote_dest_ip_addr, "value": value}

        if mote_src_ip_addr in self.automations:
            self.automations[mote_src_ip_addr].append(new_automation)
        else:
            # If no automation on this source mote is set
            self.automations[mote_src_ip_addr] = [new_automation]

        self.print_new_automation(mote_src_ip_addr, new_automation)

    def cmd_automate_activity_led(self, mote_src_ip_addr, mote_dest_ip_addr, led_color):
        value = led_color
        self.create_automation(
            "Activity to led", mote_src_ip_addr, mote_dest_ip_addr, value)

    def cmd_automate_temperature_valve(self, mote_src_ip_addr, mote_dest_ip_addr, valve_state):
        value = valve_state  # TO CHANGE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        self.create_automation("Temperature to valve",
                               mote_src_ip_addr, mote_dest_ip_addr, value)

    def cmd_exit(self):
        sys.exit()

    def cmd_invalid(self):
        print("Invalid command. Try again.")

    def print_new_automation(self, mote_src_ip_addr, automation):
        print("New automation created!" +
              "\n\t- Type: " + automation["type"] +
              "\n\t- Source mote: " + mote_src_ip_addr +
              "\n\t- Destination mote: " + automation["mote_dest_ip_addr"] +
              "\n\t- Command: " + automation["value"])

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
                "show automations": self.cmd_show_automations,
                "led/<led_ip_address>/<red|green|blue>/<on|off>": partial(self.cmd_toggle_rgb_led, mote_dest_ip_addr, led_color, led_state),
                "valve/<valve_ip_address>/<value>": partial(self.cmd_toggle_valve, mote_dest_ip_addr, valve_state),
                "automate sensor_activity/<sensor_ip_address>/led/<led_ip_address>/<red|green|blue>": partial(self.cmd_automate_activity_led, mote_src_ip_addr, mote_dest_ip_addr, led_color),
                "automate sensor_temperature/<sensor_ip_address>/valve/<valve_ip_address>/<value>": partial(self.cmd_automate_temperature_valve, mote_src_ip_addr, mote_dest_ip_addr, valve_state),
                "exit": self.cmd_exit,
            }
            switcher.get(command, self.cmd_invalid)()


def main():
    server = Server()
    server.run()


if __name__ == "__main__":
    main()
