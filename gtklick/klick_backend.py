# -*- coding: utf-8 -*-
#
# gtklick
#
# Copyright (C) 2008  Dominic Sacré  <dominic.sacre@gmx.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import liblo

import subprocess
import sys
import threading

KLICK_PATH = 'klick'
MIN_KLICK_VERSION = (0,9,0)
START_TIMEOUT = 10


class KlickBackendError:
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg


class make_method(liblo.make_method):
    def __init__(self, path, types):
        liblo.make_method.__init__(self, '/klick' + path, types)


class KlickBackend(liblo.ServerThread):
    def __init__(self, name, port, connect):
        self.addr = None
        self.ready = threading.Event()

        self.check_version()

        # call base class c'tor and start OSC server
        liblo.ServerThread.__init__(self)
        self.start()

        if not connect:
            # start klick process
            try:
                args = [
                    KLICK_PATH,
                    '-n', name,
                    '-R', self.get_url(),
                    #'-L'
                ]
                if port:
                    args += ['-o', str(port)]
                self.process = subprocess.Popen(args)
            except OSError, e:
                raise KlickBackendError("failed to start klick: %s" % e.strerror)
            # wait for klick to send /klick/ready
            if not self.wait():
                raise KlickBackendError("timeout while waiting for klick to start")
        else:
            self.process = None
            # check if klick is running
            liblo.ServerThread.send(self, port, '/klick/check')
            if not self.wait():
                raise KlickBackendError("can't connect to klick")

        # register as client
        self.send('/register_client')

    def __del__(self):
        self.quit()

    def quit(self):
        if self.addr:
            self.send('/unregister_client')
            if self.process:
                self.send('/quit')

    def check_version(self):
        try:
            output = subprocess.Popen([KLICK_PATH, '-V'], stdout=subprocess.PIPE).communicate()[0]
        except OSError, e:
            raise KlickBackendError("failed to start klick: %s\n" % e.strerror +
                                    "please make sure klick is installed")
        version_string = output.split()[1]
        version = tuple(int(x) for x in version_string.split('.'))
        if version < MIN_KLICK_VERSION:
            raise KlickBackendError("your version of klick is too old (%s).\n" % version_string + 
                                    "please upgrade to klick %d.%d.%d or later" % MIN_KLICK_VERSION)

    def check_process(self):
        return self.process and self.process.poll() == None

    def wait(self):
        for n in range(START_TIMEOUT):
            self.ready.wait(1)
            if self.addr:
                if n > 0:
                    sys.stdout.write("\n")
                return True
            sys.stdout.write(".")
            sys.stdout.flush()
        sys.stdout.write("\n")
        return False

    def send(self, path, *args):
        liblo.ServerThread.send(self, self.addr, '/klick' + path, *args)

    @make_method('/ready', '')
    def ready_cb(self, path, args, types, src):
        self.addr = src
        self.ready.set()
