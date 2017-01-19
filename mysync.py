#!/usr/bin/env python3
# vim: autoindent tabstop=5 shiftwidth=4 expandtab softtabstop=4 filetype=python
# -*- coding: utf-8 -*-

# BSD LICENSE
#
# Copyright (c) 2016, Boying Xu All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# PEP 484 -- Type Hints
# https://www.python.org/dev/peps/pep-0484/
# https://docs.python.org/3/library/typing.html


from typing import Any, Dict, Tuple, List
import sys
import functools
import logging
import asyncio
import subprocess
import asyncio.subprocess
import re
import shlex
import argparse
import fnmatch
import os
from pathlib import Path

LOOP = None  # type: asyncio.AbstractEventLoop
LOG = None  # type: logging.Logger


class GitIgnore():

    def __init__(self, fn: str):
        self.fn = fn
        self.ignorelist = ['.git/']
        self.whitelist = []
        self.update()

    def translate(self, line: str):
        line = re.sub(r'(^\s*!)', '', line)
        line = re.sub(r'\.', r'\\.', line)
        line = re.sub(r'\*', r'.*', line)
        line = re.sub(r'^\s*/(.*)$', r'^$1', line)
        return line

    def update(self):
        self.ignorelist = ['.git/']
        self.whitelist = []
        with open(self.fn, 'r') as f:
            for line in f:
                line = line.rstrip()
                if not re.search(r'^\s*#', line) and not re.search(r'^\s*$', line):
                    if re.search(r'^\s*!', line):
                        self.whitelist.append(self.translate(line))
                    else:
                        self.ignorelist.append(self.translate(line))

    def match(self, fn: str):
        for p in self.whitelist:
            if re.search(p, fn):
                return False
        for p in self.ignorelist:
            if re.search(p, fn):
                return True
        return False


class MyConfig():

    def __init__(self, local_dir: str, target_dir: str, remote: bool, ssh_tunnel_port, gitignore, dry_run):
        self.local_dir = local_dir
        self.target_dir = target_dir
        self.remote = remote
        self.ssh_tunnel_port = ssh_tunnel_port
        self.gitignore = gitignore
        self.dry_run = dry_run
        pass


CFG = None  # type: MyConfig


class PIPEProtocol(asyncio.SubprocessProtocol):

    async def run_rsync(self):
        await asyncio.sleep(1)
        stdinlist = []
        stdinlist.extend(self.PENDING.keys())
        self.PENDING.clear()
        LOG.info("Pending files begin: ")
        for x in stdinlist:
            LOG.info(x)
        LOG.info("Pending files end: ")
        cmd = []
        cmd.append("rsync")
        if CFG.remote:
            if CFG.ssh_tunnel_port:
                cmd.append("-e ssh -p %s", CFG.ssh_tunnel_port)
        cmd.append('-urvz')
        if CFG.dry_run:
            cmd.append('--dry-run')
        cmd.append("--exclude='.git/'")
        cmd.append("--progress")
        cmd.append("--files-from")
        cmd.append("-")
        cmd.append(CFG.local_dir)
        cmd.append(CFG.target_dir)
        proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE,
                                                    stdout=asyncio.subprocess.PIPE, loop=LOOP)
        proc = proc  # type: asyncio.subprocess.Process
        proc.stdin.write("\n".join(stdinlist).encode())
        proc.stdin.write_eof()
        data = await proc.stdout.read()
        line = data.decode().rstrip()
        await proc.wait()
        LOG.info(line)
        self.RSYNC_FUTURE.set_result('A')
        self.RSYNC_FUTURE = None
        return line

    def __init__(self, exit_future):
        self.exit_future = exit_future
        self.PENDING = {}
        self.RSYNC_FUTURE = None  # type: asyncio.Future

        # self.output = bytearray()

    def run_it(self, *argc):
        if len(self.PENDING.keys()) > 0:
            if not self.RSYNC_FUTURE:
                LOG.debug("Will call rsync")
                self.RSYNC_FUTURE = LOOP.create_future()
                self.RSYNC_FUTURE.add_done_callback(functools.partial(self.run_it))
                asyncio.ensure_future(self.run_rsync())
            else:
                LOG.debug("Rsync running! Will try later")

    def pipe_data_received(self, fd, data: bytes):
        cmd_str = data.decode()  # type: str
        cmd_list = []
        for x in cmd_str.split("\n"):
            M = re.search('^UPDATE:(.*)$', x)
            if M:
                pp = Path(M.group(1))
                if pp.is_dir():
                    continue
                p = str(pp.relative_to(CFG.local_dir))
                cmd_list.append(p)
        for x in cmd_list:
            if CFG.gitignore:
                if CFG.gitignore.match(x):
                    LOG.debug("Ignored file: %s" % x)
                    continue
                else:
                    self.PENDING[x] = 1
            else:
                self.PENDING[x] = 1
        self.PENDING.pop(".", None)
        self.PENDING.pop("", None)
        if len(self.PENDING.keys()) > 0:
            self.run_it()
        # self.output.extend(data)

    def process_exited(self):
        self.exit_future.set_result(True)


async def getcmd(cmd: List[str], future: asyncio.futures.Future):
    return await LOOP.subprocess_exec(lambda: PIPEProtocol(future), *cmd, stdout=asyncio.subprocess.PIPE)


async def main() -> None:
    f1 = LOOP.create_future()  # type: asyncio.Future
    f1.add_done_callback(lambda x: LOG.info("Done"))
    cmd = ['inotifywait', '-e', 'CREATE,CLOSE_WRITE,DELETE,MODIFY,MOVED_FROM,MOVED_TO',
           '-m', '-r', '--format', 'UPDATE:%w/%f', CFG.local_dir]
    transport, protocol = await getcmd(cmd=cmd, future=f1)
    # await f1
    # transport.close()
    # print(bytes(protocol.output).decode())


def prepare_logging(name: str) -> logging.Logger:
    logger = logging.getLogger(name)  # type: logging.Logger
    logger.setLevel(logging.DEBUG)
    chh = logging.StreamHandler()
    chh.setLevel(logging.INFO)
    formatterfhh = logging.Formatter(
        '[%(asctime)s] - %(name)s - {%(pathname)s:%(lineno)d} - %(levelname)s - %(message)s')
    formatterchh = logging.Formatter(' %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    formatterchh = logging.Formatter('%(filename)s:%(lineno)d:%(levelname)s - %(message)s')
    chh.setFormatter(formatterchh)
    # fhh = logging.FileHandler("%s.log" % name)
    # fhh.setLevel(logging.DEBUG)
    # fhh.setFormatter(formatterfhh)
    # logger.addHandler(fhh)
    logger.addHandler(chh)
    return logger


async def init():
    cmd = []
    cmd.append("rsync")
    if CFG.remote:
        if CFG.ssh_tunnel_port:
            cmd.append("-e ssh -p %s", CFG.ssh_tunnel_port)
    if CFG.dry_run:
        cmd.append('--dry-run')
    cmd.append('-urvz')
    cmd.append("--exclude='.git/'")
    cmd.append("--progress")
    cmd.append("--files-from")
    cmd.append("-")
    cmd.append(CFG.local_dir)
    cmd.append(CFG.target_dir)

    f = {}
    for (dirpath, dirnames, filenames) in os.walk(CFG.local_dir):
        for fn in filenames:
            x = str((Path(dirpath) / fn).relative_to(CFG.local_dir))
            if CFG.gitignore:
                if CFG.gitignore.match(x):
                    LOG.info("Ignored file: %s" % x)
                    continue
                else:
                    f[x] = 1
            else:
                f[x] = 1
    f.pop(".", None)
    LOG.info(f)
    if len(f.keys()) == 0:
        cmd = ['echo', ""]
    proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE, loop=LOOP)
    proc = proc  # type: asyncio.subprocess.Process
    proc.stdin.write("\n".join(f).encode())
    proc.stdin.write_eof()
    data = await proc.stdout.read()
    line = data.decode().rstrip()
    await proc.wait()
    LOG.info(line)
    return line


if __name__ == '__main__':

    parser = argparse.ArgumentParser(prog='mysync')
    parser.add_argument('--local_dir', type=str, nargs=1, help='local_dir(Only on this machine)', required=True)
    parser.add_argument('--target_dir', type=str, nargs=1,
                        help='target_dir(On this machine or remote machine)', required=True)
    parser.add_argument('--remote', help='If the target_dir is on remote machine, use this flag',
                        required=False, action='store_true')
    parser.add_argument('--ssh_tunnel_port', type=int, nargs=1, help='ssh tunnel port option', required=False)
    parser.add_argument('--gitignore', help='Ignore the file in local_dir/.gitignore',
                        required=False, action='store_true')
    parser.add_argument('--init', help='List all the files in local dir and sync to target',
                        required=False, action='store_true')
    parser.add_argument('--dry_run', help='Dry run, not really do the sync', required=False, action='store_true')

    args = parser.parse_args()

    local_dir = args.local_dir[0]
    target_dir = args.target_dir[0]
    gitignore = None
    if args.gitignore:
        P = Path(local_dir)
        gitignorepath = P / '.gitignore'
        if gitignorepath.is_file():
            gitignore = GitIgnore(fn=str(gitignorepath))

    if not os.path.isdir(local_dir):
        parser.error("local_dir: %s does not exist" % local_dir)

    if local_dir[-1:] != "/":
        local_dir += "/"
    if not args.remote:
        if not os.path.isdir(target_dir):
            parser.error("target_dir: %s does not exist" % target_dir)
        if target_dir[-1:] != "/":
            target_dir += "/"

    ssh_tunnel_port = args.ssh_tunnel_port[0] if args.ssh_tunnel_port else None

    CFG = MyConfig(local_dir=local_dir, target_dir=target_dir, remote=args.remote,
                   ssh_tunnel_port=ssh_tunnel_port, gitignore=gitignore, dry_run=args.dry_run)

    if sys.platform == 'win32':
        print("Windows Platform is not supported")
        sys.exit(1)
        # LOOP = asyncio.ProactorEventLoop()  # type: asyncio.windows_events.ProactorEventLoop
        # asyncio.set_event_loop(LOOP)
    else:
        LOOP = asyncio.get_event_loop()  # type: asyncio.AbstractEventLoop

    LOG = prepare_logging("program")

    if args.init:
        LOOP.run_until_complete(init())
        LOOP.close()
    else:
        asyncio.ensure_future(main())
        try:
            LOOP.run_forever()
        except KeyboardInterrupt:
            LOOP.close()
