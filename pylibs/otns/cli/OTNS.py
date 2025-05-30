#!/usr/bin/env python3
# Copyright (c) 2020-2024, The OTNS Authors.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the
#    names of its contributors may be used to endorse or promote products
#    derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from .errors import *
import ipaddress
import json
import logging
import os
import re
import readline
import shutil
import signal
import subprocess
import threading
import time
from typing import List, Union, Optional, Tuple, Dict, Any, Collection
import yaml


class OTNS(object):
    """
    OTNS creates and manages an OTNS simulation through its CLI.
    """

    MAX_SIMULATE_SPEED = 1000000  # Max simulating speed
    DEFAULT_SIMULATE_SPEED = MAX_SIMULATE_SPEED
    PAUSE_SIMULATE_SPEED = 0
    MAX_PING_DELAY = 10000  # Max delay assigned to a failed ping
    NO_CHANGE = -9223372036854775807

    CLI_PROMPT = '> '
    CLI_USER_HINT = 'OTNS command CLI - type \'exit\' to exit, or \'help\' for command overview.'

    def __init__(self, otns_path: Optional[str] = None, otns_args: Optional[List[str]] = None):
        self._closed = False
        self._cli_thread = None
        self._lock_interactive_cli = threading.Lock()
        self._lock_otns_do_command = threading.Lock()
        self.logconfig(logging.WARNING)

        self._otns_path = otns_path or self._detect_otns_path()
        default_args = ['-autogo=false', '-web=false', '-speed', str(OTNS.DEFAULT_SIMULATE_SPEED)]
        # Note: given otns_args may override i.e. revert the default_args
        self._otns_args = default_args + list(otns_args or [])
        logging.info("otns found: %s", self._otns_path)

        self._launch_otns()

    def _launch_otns(self) -> None:
        logging.info("launching otns: %s %s", self._otns_path, ' '.join(self._otns_args))
        self._otns = subprocess.Popen([self._otns_path] + self._otns_args,
                                      bufsize=16384,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE)
        logging.info("otns process launched: %s", self._otns)

    def close(self) -> None:
        """
        Close OTNS simulation.
        """
        if self._closed:
            return

        self._closed = True
        if self._cli_thread is not None and self._cli_thread is not threading.current_thread():
            logging.warning("OTNS simulation is to be closed - waiting for user CLI exit by the \'exit\' command.")
            self._cli_thread.join()
        logging.info("waiting for OTNS to close ...")
        try:
            self._do_command("exit", do_logging=False)
        except OTNSExitedError:
            pass
        time.sleep(0.010)
        self._otns.send_signal(signal.SIGTERM)
        try:
            self._otns.__exit__(None, None, None)
        except BrokenPipeError:
            pass

    def go(self, duration: float = None, speed: float = None) -> List[str]:
        """
        Continue the simulation for a period of time.

        :param duration: the time duration (in simulating time) for the simulation to continue,
                         or continue forever if duration is not specified.
        :param speed: simulating speed. Use current simulating speed if not specified.
        :return: any CLI lines output obtained during the go() period. This may be output of commands
                 running in the background, such as 'scan'. They may be 'Error' lines.
        """
        if duration is None:
            cmd = 'go ever'
        elif duration < 1e-3:
            dur_us = round(duration * 1e6)
            cmd = f'go {dur_us}us'
        else:
            cmd = f'go {duration}'

        if speed is not None:
            cmd += f' speed {speed}'

        return self._do_command(cmd, raise_cli_err=False)

    def save_pcap(self, fpath, fname) -> None:
        """
        Save the PCAP file of last simulation to the file 'fname'. Call this after close().

        :param fpath: the path where the new .pcap file will reside. Intermediate directories are created if needed.
        :param fname: the file name of the .pcap file to save to.
        """
        os.makedirs(fpath, exist_ok=True)
        shutil.copy2("current.pcap", os.path.join(fpath, fname))

    @property
    def autogo(self) -> bool:
        """
        :return: autogo setting (True=enabled)
        """
        return self._expect_int(self._do_command(f'autogo')) == 1

    @autogo.setter
    def autogo(self, is_auto: bool) -> None:
        """
        Set autogo to enabled or disabled.

        :param is_auto: True if autogo is enabled, False if disabled
        """
        self._do_command(f'autogo {int(is_auto)}')

    @property
    def speed(self) -> float:
        """
        Get simulating speed.

        :return: current simulating speed (float, '0' means paused)
        """
        speed = self._expect_float(self._do_command(f'speed'))
        if speed >= OTNS.MAX_SIMULATE_SPEED:
            return OTNS.MAX_SIMULATE_SPEED  # max speed
        elif speed <= OTNS.PAUSE_SIMULATE_SPEED:
            return OTNS.PAUSE_SIMULATE_SPEED  # paused
        else:
            return speed

    @speed.setter
    def speed(self, speed: float) -> None:
        """
        Set simulating speed.

        :param speed: new simulating speed (float). Value '0' will pause the simulation
        """
        if speed >= OTNS.MAX_SIMULATE_SPEED:
            speed = OTNS.MAX_SIMULATE_SPEED
        elif speed <= 0:
            speed = OTNS.PAUSE_SIMULATE_SPEED

        self._do_command(f'speed {speed}')

    @property
    def radiomodel(self) -> str:
        """
        Get radiomodel used for simulation.

        :return: current radio model used
        """
        return self._expect_str(self._do_command(f'radiomodel'))

    @radiomodel.setter
    def radiomodel(self, model: str) -> None:
        """
        Set radiomodel to be used for simulation. Setting a radiomodel also resets all the
        radiomodel parameters.

        :param model: name of new radio model to use. Default is "MutualInterference".
                      See CLI Readme or type 'help radiomodel' to see the options.
        """
        assert self._do_command(f'radiomodel {model}')[0] == model

    def radioparams(self) -> Dict[str, float]:
        """
        Get radiomodel parameters.

        :return: dict with parameter strings as keys and parameter values as values
        """
        output = self._do_command('radioparam')
        params = {}
        for line in output:
            line = line.split()
            parname = line[0]
            parvalue = float(line[1])
            params[parname] = parvalue
        return params

    def get_radioparam(self, parname: str) -> float:
        """
        Get a radiomodel parameter.

        :param parname: name (string) of radiomodel parameter
        :return parameter value (float)
        """
        return float(self._do_command(f'radioparam {parname}')[0])

    def set_radioparam(self, parname: str, parvalue: float) -> None:
        """
        Set a radiomodel parameter to the specified value.

        :param parname: name (string) of the radiomodel parameter
        :param parvalue: parameter value (float) to be set
        """
        self._do_command(f'radioparam {parname} {parvalue}')

    @property
    def loglevel(self) -> str:
        """
        Get current log-level.

        :return: current log-level setting for OT-NS and Node log messages.
        """
        level = self._expect_str(self._do_command(f'log'))
        return level

    @loglevel.setter
    def loglevel(self, level: str) -> None:
        """
        Set log-level for all OT-NS and Node log messages.
        Note: this is set independent from OTNS.logconfig().

        :param level: new log-level name, debug | info | warn | error
        """
        self._do_command(f'log {level}')

    def logconfig(self, level: int = logging.INFO) -> None:
        """
        Configure Python logging package to display the pyOTNS internal log messages.
        This may override existing configuration of the 'logging' package.

        :param level: a log level value that defines what to log, e.g. logging.DEBUG.
        """
        logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    @property
    def time(self) -> int:
        """
        Get simulation time.

        :return: current simulation time in seconds (us resolution)
        """
        return self._expect_int(self._do_command(f'time')) / 1.0e6

    def set_poll_period(self, nodeid: int, period: float) -> None:
        ms = int(period * 1000)
        self.node_cmd(nodeid, f'pollperiod {ms}')

    def get_poll_period(self, nodeid: int) -> float:
        ms = self._expect_int(self.node_cmd(nodeid, 'pollperiod'))
        return ms / 1000.0

    @staticmethod
    def _detect_otns_path() -> str:
        env_otns_path = os.getenv('OTNS')
        if env_otns_path:
            return env_otns_path

        which_otns = shutil.which('otns')
        if not which_otns:
            raise RuntimeError("otns not found in current directory and PATH")

        return which_otns

    def _do_command(self,
                    cmd: str,
                    do_logging: bool = True,
                    raise_cli_err: bool = True,
                    output_donestrings: bool = False,
                    force_global_scope: bool = True) -> List[str]:
        if force_global_scope and len(cmd) > 0 and cmd[0] != '!':
            cmd = '!' + cmd

        with self._lock_otns_do_command:
            if do_logging:
                logging.info("OTNS <<< %s", cmd)
            try:
                self._otns.stdin.write(cmd.encode('ascii') + b'\n')
                self._otns.stdin.flush()
            except (IOError, BrokenPipeError, ValueError):
                self._on_otns_eof()

            output = []
            if cmd == '':
                return output

            while True:
                try:
                    line = self._otns.stdout.readline()
                except (IOError, BrokenPipeError):
                    self._on_otns_eof()
                if line == b'':
                    self._on_otns_eof()

                line = line.rstrip(b'\r\n').decode('utf-8')
                if do_logging:
                    logging.info(f"OTNS >>> {line}")
                if line == 'Done' or line == 'Started':
                    if output_donestrings:
                        output.append(line)
                    return output
                elif line.startswith('Error: ') or line.startswith('Error '):
                    if raise_cli_err:
                        raise create_otns_cli_error(line)
                    output.append(line)
                    return output

                output.append(line)

    def cmd(self, cmd: str) -> List[str]:
        """
        Execute an arbitrary OTNS CLI command and return the resulting output lines (if any).

        :param cmd: the command line string to execute in OTNS.
        :return: output lines from OTNS with command result, if any. The "Done" or "Error" strings are not
                returned. In case the command execution lead to an error, OTNSCliError is raised. In case
                OTNS exited while processing the command, OTNSCommandInterruptedError is raised. See
                errors.py for more possibilites (all are subclass of OTNSError).
        """
        return self._do_command(cmd)

    def _interactive_cli_thread(self, prompt: str, close_otns_on_exit: bool) -> None:
        cur_prompt = prompt
        is_global_context = True  # tracks the context of the prompt: global, or node-specific.
        while True:
            cmd = input(cur_prompt)
            if cmd == 'exit' and is_global_context:
                break
            if cmd == '':
                # force a 'Done' from OTNS. This allows collecting async outputlines with Enter key.
                output_lines = self._do_command('debug',
                                                raise_cli_err=False,
                                                do_logging=False,
                                                output_donestrings=False)
            else:
                output_lines = self._do_command(cmd,
                                                raise_cli_err=False,
                                                do_logging=True,
                                                output_donestrings=True,
                                                force_global_scope=False)

            # CLI context tracking - only done to display the right prompt (node-context) to user
            if cmd == 'node 0' or cmd == 'exit':
                is_global_context = True
                cur_prompt = prompt
            elif cmd.startswith('node ') and output_lines[0] == 'Done':
                is_global_context = False
                cur_prompt = cmd + prompt

            for line in output_lines:
                print(line)

        if close_otns_on_exit:
            self.close()
        self._cli_thread = None

    def interactive_cli(self,
                        prompt: Optional[str] = CLI_PROMPT,
                        user_hint: Optional[str] = CLI_USER_HINT,
                        close_otns_on_exit: Optional[bool] = False) -> bool:
        """
        Start an interactive CLI and GUI session, where the user can control the simulation until the
        exit command is typed.

        :param prompt: (optional) custom prompt string
        :param user_hint: (optional) user hint about being in CLI mode
        :param close_otns_on_exit: (optional) behavior to close OTNS when user exits the CLI.
        :return: True if interactive CLI was started and concluded, False if it could not be
                 started (e.g. already running via a thread).
        """
        with self._lock_interactive_cli:
            if self._cli_thread is not None:
                return False
            readline.set_auto_history(True)  # using Python readline library for CLI history on input().
            print(user_hint)
            self._interactive_cli_thread(prompt, close_otns_on_exit)

        return True

    def interactive_cli_threaded(self,
                                 prompt: Optional[str] = CLI_PROMPT,
                                 user_hint: Optional[str] = CLI_USER_HINT,
                                 close_otns_on_exit: Optional[bool] = True) -> bool:
        """
        Start an interactive CLI and GUI session in a new thread. The user can now control the simulation
        using CLI and GUI, while the Python script also operates on the simulation in parallel. If the
        user types 'exit' the OTNS simulation will be closed.

        :param prompt: (optional) custom prompt string
        :param user_hint: (optional) user hint about being in CLI mode
        :param close_otns_on_exit: (optional) behavior to close OTNS when user exits the CLI.
        :return: True if thread could be started, False if not (e.g. already running).
        """
        with self._lock_interactive_cli:
            if self._cli_thread is not None:
                return False
            readline.set_auto_history(True)  # using Python readline library for CLI history on input().

            self._cli_thread = threading.Thread(target=self._interactive_cli_thread, args=(prompt, close_otns_on_exit))
            print(user_hint)
            self._cli_thread.start()

            return True

    def add(self,
            type: str,
            x: float = None,
            y: float = None,
            id=None,
            radio_range=None,
            executable=None,
            restore=False,
            txpower: int = None,
            version: str = None,
            deviceModel: str = None,
            script: str = None) -> int:
        """
        Add a new node to the simulation.

        :param type: node type
        :param x: node position X
        :param y: node position Y
        :param id: node ID, or None to use next available node ID
        :param radio_range: node radio range or None for default
        :param executable: specify the executable for the new node, or use default executable if None
        :param restore: whether the node restores network configuration from persistent storage
        :param txpower: Tx power in dBm of node, or None for OT node default
        :param version: optional OT node version string like 'v11', 'v12', 'v13', or 'v14', etc.
        :param deviceModel: specify device model for energy calculations.
        :param script: optional OT node init script as a single string.
        :return: added node ID
        """
        cmd = f'add {type}'
        if x is not None:
            cmd = cmd + f' x {x}'
        if y is not None:
            cmd = cmd + f' y {y}'

        if id is not None:
            cmd += f' id {id}'

        if radio_range is not None:
            cmd += f' rr {radio_range}'

        if executable:
            cmd += f' exe "{executable}"'

        if restore:
            cmd += f' restore'

        if version is not None:
            cmd += f' {version}'

        if deviceModel is not None:
            cmd += f' dm "{deviceModel}"'

        if script is not None:
            cmd += ' raw'

        nodeid = self._expect_int(self._do_command(cmd))

        if script is not None:
            self.node_script(nodeid, script)

        if txpower is not None:
            self.node_cmd(nodeid, f'txpower {txpower}')

        return nodeid

    def delete(self, *nodeids: int) -> None:
        """
        Delete nodes from simulation by IDs.

        :param nodeids: node IDs
        """
        cmd = f'del {" ".join(map(str, nodeids))}'
        self._do_command(cmd)

    def delete_all(self) -> None:
        """
        Delete all nodes from simulation.
        """
        self._do_command('del all')

    def watch(self, *nodeids: int) -> None:
        """
        Enable watch on nodes from simulation by IDs.

        :param nodeids: node IDs
        """
        cmd = f'watch {" ".join(map(str, nodeids))}'
        self._do_command(cmd)

    def watch_all(self, level: str) -> None:
        """
        Set watch log level on all current nodes.

        :param level: watch log level 'trace', 'debug', 'info', 'warn', 'crit', or 'off'.
        """
        cmd = f'watch all {level}'
        self._do_command(cmd)

    def watch_default(self, level: str) -> None:
        """
        Set default watch log level for newly to be created nodes.

        :param level: watch log level 'trace', 'debug', 'info', 'warn', 'crit', or 'off'.
        """
        cmd = f'watch default {level}'
        self._do_command(cmd)

    def watched(self) -> List[int]:
        """
        Get the nodes currently being watched.

        :return: watched node IDs
        """
        cmd = f'watch'
        ids_str = self._do_command(cmd)[0]
        if len(ids_str) == 0:
            return []
        return list(map(int, ids_str.split(" ")))

    def unwatch(self, *nodeids: int) -> None:
        """
        Disable watch (unwatch) nodes from simulation by IDs.

        :param nodeids: node IDs
        """
        cmd = f'unwatch {" ".join(map(str, nodeids))}'
        self._do_command(cmd)

    def unwatch_all(self) -> None:
        """
        Disable watch (unwatch) on all nodes.
        """
        cmd = f'unwatch all'
        self._do_command(cmd)

    def move(self, nodeid: int, x: int, y: int, z: int = NO_CHANGE) -> None:
        """
        Move node to the 2D, or 3D, target position.

        :param nodeid: target node ID
        :param x: target position X
        :param y: target position Y
        :param z: (optional) target position Z
        """
        if z == OTNS.NO_CHANGE:
            cmd = f'move {nodeid} {x} {y}'
        else:
            cmd = f'move {nodeid} {x} {y} {z}'
        self._do_command(cmd)

    def ping(self,
             srcid: int,
             dst: Union[int, str, ipaddress.IPv6Address],
             addrtype: str = 'any',
             datasize: int = 4,
             count: int = 1,
             interval: float = 10) -> None:
        """
        Ping from source node to destination node.

        :param srcid: source node ID
        :param dst: destination node ID or address
        :param addrtype: address type for the destination node (only useful for destination node ID)
        :param datasize: ping data size; WARNING - data size < 4 is ignored by OTNS.
        :param count: ping count
        :param interval: ping interval (in seconds), also the max acceptable ping RTT before giving up.

        Use pings() to get ping results.
        """
        if isinstance(dst, (str, ipaddress.IPv6Address)):
            addrtype = ''  # addrtype only appliable for dst ID

            if isinstance(dst, ipaddress.IPv6Address):
                dst = dst.compressed

        cmd = f'!ping {srcid} {dst!r} {addrtype} datasize {datasize} count {count} interval {interval}'
        self._do_command(cmd)

    @property
    def packet_loss_ratio(self) -> float:
        """
        Get the message drop ratio of 128 byte packet.
        Smaller packet has lower drop ratio.

        :return: message drop ratio (0 ~ 1.0)
        """
        return self._expect_float(self._do_command('plr'))

    @packet_loss_ratio.setter
    def packet_loss_ratio(self, value: float) -> None:
        """
        Set the message drop ratio of 128 byte packet.
        Smaller packet has lower drop ratio.

        :param value: message drop ratio (0 ~ 1.0)
        """
        self._do_command(f'plr {value}')

    def nodes(self) -> Dict[int, Dict[str, Any]]:
        """
        Get all nodes in simulation

        :return: dict with node IDs as keys and node information as values
        """
        cmd = 'nodes'
        output = self._do_command(cmd)
        nodes = {}
        for line in output:
            nodeinfo = {}
            for kv in line.split():
                k, v = kv.split('=')
                if k in ('id', 'x', 'y', 'z'):
                    v = int(v)
                elif k in ('extaddr', 'rloc16'):
                    v = int(v, 16)
                elif k in ('failed',):
                    v = v == 'true'
                elif k in ('ct_interval', 'ct_delay'):
                    v = float(v)
                else:
                    pass

                nodeinfo[k] = v

            nodes[nodeinfo['id']] = nodeinfo

        return nodes

    def partitions(self) -> Dict[int, Collection[int]]:
        """
        Get partitions.

        :return: dict with partition IDs as keys and node list as values
        """
        output = self._do_command('partitions')
        partitions = {}
        for line in output:
            line = line.split()
            assert line[0].startswith('partition=') and line[1].startswith('nodes='), line
            parid = int(line[0].split('=')[1], 16)
            nodeids = list(map(int, line[1].split('=')[1].split(',')))
            partitions[parid] = nodeids

        return partitions

    def radio_on(self, *nodeids: int) -> None:
        """
        Turn on node radio.

        :param nodeids: operating node IDs
        """
        self._do_command(f'radio {" ".join(map(str, nodeids))} on')

    def radio_off(self, *nodeids: int) -> None:
        """
        Turn off node radio.

        :param nodeids: operating node IDs
        """
        self._do_command(f'radio {" ".join(map(str, nodeids))} off')

    def radio_set_fail_time(self, *nodeids: int, fail_time: Optional[Tuple[int, int]]) -> None:
        """
        Set node radio fail time parameters.

        :param nodeids: node IDs
        :param fail_time: fail time (fail_duration, fail_interval) or None for always on.
        """
        fail_duration, period_time = fail_time
        cmd = f'radio {" ".join(map(str, nodeids))} ft {fail_duration} {period_time}'
        self._do_command(cmd)

    def pings(self) -> List[Tuple[int, str, int, float]]:
        """
        Get ping results.

        :return: list of ping results, each of format (node ID, destination address, data size, delay)
        """
        output = self._do_command('pings')
        pings = []
        for line in output:
            line = line.split()
            pings.append((
                int(line[0].split('=')[1]),
                line[1].split('=')[1],
                int(line[2].split('=')[1]),
                float(line[3].split('=')[1][:-2]),
            ))

        return pings

    def print_pings(self, pings):
        """
        Print a set of ping results, obtained via pings().
        """
        for p in pings:
            time_ms = round(p[3])
            print(f"ping {p[0]} {p[1]}\tdatasz={p[2]}\t{time_ms} ms")

    def joins(self) -> List[Tuple[int, float, float]]:
        """
        Get join results.

        :return: list of join results, each of format (node ID, join time, session time)
        """
        output = self._do_command('joins')
        joins = []
        for line in output:
            line = line.split()
            joins.append((
                int(line[0].split('=')[1]),
                float(line[1].split('=')[1][:-1]),
                float(line[2].split('=')[1][:-1]),
            ))

        return joins

    def counters(self) -> Dict[str, int]:
        """
        Get counters.

        :return: dict of all counters
        """
        output = self._do_command('counters')
        counters = {}
        for line in output:
            name, val = line.split()
            val = int(val)
            counters[name] = val

        return counters

    def prefix_add(self,
                   nodeid: int,
                   prefix: str,
                   preferred=True,
                   slaac=True,
                   dhcp=False,
                   dhcp_other=False,
                   default_route=True,
                   on_mesh=True,
                   stable=True,
                   prf='med') -> None:
        """
        Add a prefix to the network data of a node and register the updated network data with the Leader.

        :param nodeid: Node ID
        :param prefix: the IPv6 prefix to add
        :param preferred: P_preferred flag
        :param slaac: P_slaac flag
        :param dhcp: P_dhcp flag
        :param dhcp_other: P_configure flag
        :param default_route: P_default flag
        :param on_mesh: P_on_mesh flag
        :param stable: P_stable flag
        :param prf: P_preference value (hi/med/low)
        """
        flags = ''
        if preferred:
            flags += 'p'
        if slaac:
            flags += 'a'
        if dhcp:
            flags += 'd'
        if dhcp_other:
            flags += 'c'
        if default_route:
            flags += 'r'
        if on_mesh:
            flags += 'o'
        if stable:
            flags += 's'

        assert flags
        assert prf in ('high', 'med', 'low')

        cmd = f'prefix add {prefix} {flags} {prf}'
        self.node_cmd(nodeid, cmd)
        self.node_cmd(nodeid, 'netdata register')

    def node_cmd(self, nodeid: int, cmd: str) -> List[str]:
        """
        Run command on node.

        :param nodeid: target node ID
        :param cmd: command to execute
        :return: lines of command output
        """
        cmd = f'node {nodeid} "{cmd}"'
        output = self._do_command(cmd)
        return output

    def node_script(self, nodeid: int, script: str) -> List[str]:
        """
        Run script of one or more commands on node.

        :param nodeid: target node ID
        :param script: script to execute
        :return: lines of command output
        """
        output = []
        lines = script.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) == 0 or line[0] == '#':
                continue
            output_one = self.node_cmd(nodeid, line)
            for o in output_one:
                output.append(o)

        return output

    def get_state(self, nodeid: int) -> str:
        """
        Get node state.

        :param nodeid: node ID
        """
        output = self.node_cmd(nodeid, "state")
        return self._expect_str(output)

    def get_rloc16(self, nodeid: int) -> int:
        """
        Get node RLOC16.

        :param nodeid: node ID
        :return: node RLOC16
        """
        return self._expect_hex(self.node_cmd(nodeid, "rloc16"))

    def get_ipaddrs(self, nodeid: int, addrtype: str = None) -> List[ipaddress.IPv6Address]:
        """
        Get node ipaddrs.

        :param nodeid: node ID
        :param addrtype: address type (one of mleid, rloc, linklocal), or None for all addresses
        :return: list of filtered addresses
        """
        cmd = "ipaddr"
        if addrtype:
            cmd += f' {addrtype}'

        return [ipaddress.IPv6Address(a) for a in self.node_cmd(nodeid, cmd)]

    def get_mleid(self, nodeid: int) -> ipaddress.IPv6Address:
        """
        Get the MLEID of a node.

        :param nodeid: the node ID
        :return: the MLEID
        """
        ips = self.get_ipaddrs(nodeid, 'mleid')
        return ips[0] if ips else None

    def set_network_name(self, nodeid: int, name: str = None) -> None:
        """
        Set network name.

        :param nodeid: node ID
        :param name: network name to set
        """
        name = self._escape_whitespace(name)
        self.node_cmd(nodeid, f'networkname {name}')

    def get_network_name(self, nodeid: int) -> str:
        """
        Get network name.

        :param nodeid: node ID
        :return: network name
        """
        return self._expect_str(self.node_cmd(nodeid, 'networkname'))

    def set_panid(self, nodeid: int, panid: int) -> None:
        """
        Set node pan ID.

        :param nodeid: node ID
        :param panid: pan ID
        """
        self.node_cmd(nodeid, 'panid 0x%04x' % panid)

    def set_extpanid(self, nodeid: int, extpanid: int) -> None:
        """
        Set node extended pan ID.

        :param nodeid: node ID
        :param extpanid: extended pan ID
        """
        self.node_cmd(nodeid, 'extpanid %016x' % extpanid)

    def get_panid(self, nodeid: int) -> int:
        """
        Get node pan ID.

        :param nodeid: node ID
        :return: pan ID
        """
        return self._expect_hex(self.node_cmd(nodeid, 'panid'))

    def set_channel(self, nodeid: int, channel: int) -> None:
        """
        Set node channel.

        :param nodeid: node ID
        :param channel: IEEE 802.15.4 channel number
        """
        self.node_cmd(nodeid, 'channel %d' % channel)

    def get_channel(self, nodeid: int) -> int:
        """
        Get node pan ID.

        :param nodeid: node ID
        :return: IEEE 802.15.4 channel number
        """
        return self._expect_hex(self.node_cmd(nodeid, 'channel'))

    def get_extpanid(self, nodeid: int) -> int:
        """
        Get node extended pan ID.

        :param nodeid: node ID
        :return: extended pan ID
        """
        return self._expect_hex(self.node_cmd(nodeid, 'extpanid'))

    def get_networkkey(self, nodeid: int) -> str:
        """
        Get network key.

        :param nodeid: target node ID
        :return: network key as a hex string (without '0x' prefix)
        """
        return self._expect_str(self.node_cmd(nodeid, 'networkkey'))

    def set_networkkey(self, nodeid: int, key: str) -> None:
        """
        Set network key.

        :param nodeid: target node ID
        :param key: network key as a hex string (without '0x' prefix)
        """
        self.node_cmd(nodeid, f'networkkey {key}')

    def config_dataset(self,
                       nodeid: int,
                       channel: int = None,
                       panid: int = None,
                       extpanid: str = None,
                       networkkey: str = None,
                       network_name: str = None,
                       active_timestamp: int = None,
                       set_remaining: bool = False,
                       dataset: str = 'active'):
        """
        Configure the active or pending dataset. Parameters not provided (or set to None) are not set in the
        resulting dataset.

        :param nodeid: target node ID
        :param channel: the channel number.
        :param panid: the Pan ID.
        :param extpanid: the Extended PAN ID.
        :param networkkey: the network key (REQUIRED)
        :param network_name: the network name
        :param active_timestamp: the active timestamp.
        :param set_remaining: if True, sets remaining dataset items not listed in params here to
                              default values. If False, does not set these items.
        :param dataset: use 'active' for Active Dataset or 'pending' for Pending Dataset.
        """
        assert dataset in ('active', 'pending'), dataset

        self.node_cmd(nodeid, 'dataset clear')

        if channel is not None:
            self.node_cmd(nodeid, f'dataset channel {channel}')

        if panid is not None:
            self.node_cmd(nodeid, f'dataset panid 0x{panid:04x}')

        if extpanid is not None:
            self.node_cmd(nodeid, f'dataset extpanid {extpanid}')

        if networkkey is not None:
            self.node_cmd(nodeid, f'dataset networkkey {networkkey}')

        if network_name is not None:
            network_name = self._escape_whitespace(network_name)
            self.node_cmd(nodeid, f'dataset networkname {network_name}')

        if active_timestamp is not None:
            self.node_cmd(nodeid, f'dataset activetimestamp {active_timestamp}')

        if set_remaining:
            self.node_cmd(nodeid, f'dataset channelmask 0x07fff800')
            self.node_cmd(nodeid, f'dataset meshlocalprefix fdde:ad00:beef:0::')
            self.node_cmd(nodeid, f'dataset pskc 3aa55f91ca47d1e4e71a08cb35e91591')
            self.node_cmd(nodeid, f'dataset securitypolicy 672 onrc 0')

        self.node_cmd(nodeid, f'dataset commit {dataset}')

    def web(self, tab_name: str = "") -> None:
        """
        Open web browser for visualization.

        :param tab_name: name of tab/page to open (optional). Use 'main', 'stats', or 'energy'.
        """
        self._do_command(f'web {tab_name}')

    def web_display(self) -> None:
        """
        Wait for web browser display/rendering of current topology/situation to be done.
        TODO: currently uses a heuristic method and it's not verified that the web browser has actually rendered.
        """
        self._do_command('go 0us speed 1')  # a 'go' triggers a PostAsyncWait and sends an advance-time event to viz.
        time.sleep(0.020)

    def ifconfig_up(self, nodeid: int) -> None:
        """
        Turn up network interface.

        :param nodeid: target node ID
        """
        self.node_cmd(nodeid, 'ifconfig up')

    def ifconfig_down(self, nodeid: int) -> None:
        """
        Turn down network interface.

        :param nodeid: target node ID
        """
        self.node_cmd(nodeid, 'ifconfig down')

    def thread_start(self, nodeid: int) -> None:
        """
        Start thread.

        :param nodeid: target node ID
        """
        self.node_cmd(nodeid, 'thread start')

    def thread_stop(self, nodeid: int) -> None:
        """
        Stop thread.

        :param nodeid: target node ID
        """
        self.node_cmd(nodeid, 'thread stop')

    def commissioner_start(self, nodeid: int) -> None:
        """
        Start commissioner.

        :param nodeid: target node ID
        """
        self.node_cmd(nodeid, "commissioner start")

    def joiner_start(self, nodeid: int, pwd: str) -> None:
        """
        Start joiner.

        :param nodeid: joiner node ID
        :param pwd: commissioning password
        """
        self.node_cmd(nodeid, f"joiner start {pwd}")

    def joiner_startccm(self, nodeid: int) -> None:
        """
        Start CCM joiner, using Autonomous Enrollment (AE) with cBRSKI.

        :param nodeid: joiner node ID
        """
        self.node_cmd(nodeid, f"joiner startccm")

    def commissioner_joiner_add(self, nodeid: int, usr: str, pwd: str, timeout=None) -> None:
        """
        Add joiner to commissioner.

        :param nodeid: commissioner node ID
        :param usr: joiner EUI-64 or discerner (id) or '*' for any joiners
        :param pwd: commissioning password
        :param timeout: commissioning session timeout
        """
        timeout_s = f" {timeout}" if timeout is not None else ""
        self.node_cmd(nodeid, f"commissioner joiner add {usr} {pwd}{timeout_s}")

    def commissioner_ccm_joiner_add(self, nodeid: int, usr: str, timeout=None) -> None:
        """
        Add CCM joiner to commissioner.

        :param nodeid: commissioner node ID
        :param usr: joiner EUI-64 or discerner (id) or '*' for any joiners
        :param pwd: commissioning password
        :param timeout: commissioning session timeout
        """
        timeout_s = f" {timeout}" if timeout is not None else ""
        self.node_cmd(nodeid, f"commissioner joiner add {usr} CCMCCM{timeout_s}")

    def config_visualization(self, broadcast_message: bool = None, unicast_message: bool = None,
                             ack_message: bool = None, router_table: bool = None, child_table: bool = None) \
            -> Dict[str, bool]:
        """
        Configure the visualization options.

        :param broadcast_message: whether or not to visualize broadcast messages
        :param unicast_message: whether or not to visualize unicast messages
        :param ack_message: whether or not to visualize ACK messages
        :param router_table: whether or not to visualize router tables
        :param child_table: whether or not to visualize child tables

        :return: the active visualization options
        """
        cmd = "cv"
        if broadcast_message is not None:
            cmd += " bro " + ("on" if broadcast_message else "off")

        if unicast_message is not None:
            cmd += " uni " + ("on" if unicast_message else "off")

        if ack_message is not None:
            cmd += " ack " + ("on" if ack_message else "off")

        if router_table is not None:
            cmd += " rtb " + ("on" if router_table else "off")

        if child_table is not None:
            cmd += " ctb " + ("on" if child_table else "off")

        output = self._do_command(cmd)
        vopts = {}
        for line in output:
            line = line.split('=')
            assert len(line) == 2 and line[1] in ('on', 'off'), line
            vopts[line[0]] = (line[1] == "on")

        # convert command options to python options
        vopts['broadcast_message'] = vopts.pop('bro')
        vopts['unicast_message'] = vopts.pop('uni')
        vopts['ack_message'] = vopts.pop('ack')
        vopts['router_table'] = vopts.pop('rtb')
        vopts['child_table'] = vopts.pop('ctb')

        return vopts

    def set_title(self, title: str, x: int = None, y: int = None, font_size: int = None) -> None:
        """
        Set simulation title.

        :param title: title text
        :param x: X coordinate of title
        :param y: Y coordinate of title
        :param font_size: Font size of title
        """
        cmd = f'title "{title}"'

        if x is not None:
            cmd += f' x {x}'

        if y is not None:
            cmd += f' y {y}'

        if font_size is not None:
            cmd += f' fs {font_size}'

        self._do_command(cmd)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def get_router_upgrade_threshold(self, nodeid: int) -> int:
        """
        Get Router upgrade threshold.

        :param nodeid: the node ID
        :return: the Router upgrade threshold
        """
        return self._expect_int(self.node_cmd(nodeid, 'routerupgradethreshold'))

    def set_router_upgrade_threshold(self, nodeid: int, val: int) -> None:
        """
        Set Router upgrade threshold.

        :param nodeid: the node ID
        :param val: the Router upgrade threshold
        """
        self.node_cmd(nodeid, f'routerupgradethreshold {val}')

    def get_router_downgrade_threshold(self, nodeid: int) -> int:
        """
        Get Router downgrade threshold.

        :param nodeid: the node ID
        :return: the Router downgrade threshold
        """
        return self._expect_int(self.node_cmd(nodeid, 'routerdowngradethreshold'))

    def set_router_downgrade_threshold(self, nodeid: int, val: int) -> None:
        """
        Set Router downgrade threshold.

        :param nodeid: the node ID
        :param val: the Router downgrade threshold
        """
        self.node_cmd(nodeid, f'routerdowngradethreshold {val}')

    def get_thread_version(self, nodeid: int) -> int:
        """
        Get Thread version (integer) of a node.

        :param nodeid: the node ID
        :return: the Thread version
        """
        return self._expect_int(self.node_cmd(nodeid, 'thread version'))

    def get_node_uptime(self, nodeid: int) -> int:
        """
        Get a node's self-reported uptime in seconds. Resolution is milliseconds.

        :param nodeid: the node ID
        :return: the uptime in seconds (converted from node's Dd.hh:mm:ss.ms format)
        """
        uptime_str = self._expect_str(self.node_cmd(nodeid, 'uptime'))
        # example 'uptime' command OT node output: 1d.00:33:20.020
        m = re.search('((\d+)d\.)?(\d\d):(\d\d):(\d\d)\.(\d\d\d)', uptime_str)
        assert m is not None, uptime_str
        g = m.groups()
        time_sec = int(g[2]) * 3600 + int(g[3]) * 60 + int(g[4]) + int(g[5]) / 1000.0
        if g[1] is not None:
            time_sec += int(g[1]) * 24 * 3600
        return round(time_sec, 3)

    def set_node_clock_drift(self, nodeid: int, drift: int):
        """
        Set the clock drift (in PPM) for a node.

        :param nodeid: the Node ID
        :param drift: the clock drift in PPM (integer < 0, 0 or > 0)
        :return:
        """
        self._do_command(f'rfsim {nodeid} clkdrift {drift}')

    def coaps_enable(self) -> None:
        """
        Enable the 'coaps' function of OTNS to collect info about CoAP messages.
        """
        self._do_command('coaps enable')

    def coaps(self) -> List[Dict]:
        """
        Get recent CoAP messages collected by OTNS. The 'coaps' function should be enabled prior to
        calling this.

        :return: a List of CoAP messages. Each message is a Dict with metadata about the message.
        """
        lines = self._do_command('coaps')
        messages = yaml.safe_load('\n'.join(lines))
        return messages

    def kpi_start(self) -> None:
        """
        Start OTNS KPI collection.
        """
        self._do_command('kpi start')

    def kpi_stop(self) -> None:
        """
        Stop OTNS KPI collection.
        """
        self._do_command('kpi stop')

    def kpi_save(self, filename: str = None) -> Dict:
        """
        Save collected OTNS KPI data to a JSON file.

        @:param filename the name of the file to save to or None for no filename provided (This will save to
        the OTNS default file ?_kpi.json)
        """
        if filename is None:
            filename = 'tmp/0_kpi.json'  # TODO: 0_ only works for default -listen port 9000.
            self._do_command('kpi save')
        else:
            self._do_command(f'kpi save "{filename}"')

        f = open(filename)
        j = json.load(f)
        f.close()
        return j

    def kpi(self) -> bool:
        """
        Get the status of OTNS KPI collection.

        :return: True if KPI collection is running/started, False if not-running/stopped.
        """
        status = self._expect_str(self._do_command('kpi'))
        return status == 'on'

    def load(self, filename: str) -> None:
        """
        Load new nodes / network topology from a YAML file.

        :param filename: file name to load from
        """
        self._do_command(f'load "{filename}"')

    def save(self, filename: str) -> None:
        """
        Save nodes / network topology to a YAML file.

        :param filename: file name to save to
        """
        self._do_command(f'save "{filename}"')

    @staticmethod
    def _expect_int(output: List[str]) -> int:
        assert len(output) == 1, output
        return int(output[0])

    @staticmethod
    def _expect_hex(output: List[str]) -> int:
        assert len(output) == 1, output
        return int(output[0], 16)

    @staticmethod
    def _expect_float(output: List[str]) -> float:
        assert len(output) == 1, output
        return float(output[0])

    @staticmethod
    def _expect_str(output: List[str]) -> str:
        assert len(output) == 1, output
        return output[0].strip()

    @staticmethod
    def _escape_whitespace(s: str) -> str:
        """
        Escape string by replace <whitespace> by \\<whitespace>.

        :param s: string to escape
        :return: the escaped string
        """
        for c in "\\ \t\r\n":
            s = s.replace(c, '\\' + c)
        return s

    def _on_otns_eof(self):
        exit_code = self._otns.wait()
        if exit_code < 0:
            logging.warning("otns exited due to termination signal: code = %d", exit_code)
        else:
            logging.warning("otns exited: code = %d", exit_code)
        raise OTNSExitedError(exit_code)


if __name__ == '__main__':
    import doctest

    doctest.testmod()
