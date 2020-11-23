#!/usr/bin/env python3
from datetime import datetime
from functools import partial
import subprocess
import time

import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify

IGNORED_FACTS = ['valid_lft']
IGNORED_NICS = ['lo', 'virbr0']


def exec(cmd):
    raw = subprocess.Popen(
        ['ip', 'a'],
        stdout=subprocess.PIPE).communicate()[0]
    return str(raw).split('\\n')


class Ipa(object):

    expire_after = 30

    def __init__(self, handler=None):
        self._facts = {}
        self._last_update = None
        if handler:
            self._handler = handler
        self.update()

    @property
    def nics(self):
        self._update_if_expired()
        return self._facts.keys()

    def __getitem__(self, key):
        self._update_if_expired()
        return self._facts[key]

    def _update_if_expired(self):
        if not self._last_update or (self._last_update - datetime.now()).seconds > self.expire_after:
            self.update()

    def update(self):
        data = exec(['ip', 'a'])
        nic = None
        new_facts = {}

        for line in data:
            if len(line) <= 1:
                # empty line
                continue

            if line[0] != " ":
                # start of new nic entry
                if nic and new_facts != self._facts.get(nic):
                    # save last entry
                    self._handler(nic, new_facts)
                    self._facts[nic] = new_facts

                # prepare to read a new entry
                line = line.strip().split(':')
                nic = str(line[1]).strip()
                new_facts = {}
                if nic in IGNORED_NICS:
                    nic = None
                else:
                    new_facts['@'] = line[2]
           
            elif nic is not None:
                # read nic data line
                line = line.strip().split()
                fact = str(line[0])
                if fact not in IGNORED_FACTS:
                    new_facts[fact] = line[1:]

        self._last_update = datetime.now()

    def _handler(self, nic, facts):
        pass
            

class Main(object):
    def __init__(self):
        self.notis = {}
        self.ipa = Ipa(self.nic_changed)

    def nic_changed(self, nic, facts):
        # get new ip address
        inet = facts.get('inet')
        if inet:
            ipaddr = inet[0]
        else:
            ipaddr = None

        # cancel previous notification
        if nic in self.notis:
            noti = self.notis.pop(nic)
            noti.close()

        # raise new notification
        if ipaddr:
            noti = Notify.Notification.new(nic, ipaddr)
            self.notis[nic] = noti
            noti.show()

    def run(self):
        while True:
            time.sleep(5)
            self.ipa.update()

if __name__ == "__main__":
    Notify.init('IP Watcher')
    Main().run()
    Notify.uninit()
