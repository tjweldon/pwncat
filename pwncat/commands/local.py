#!/usr/bin/env python3
import subprocess

from pwncat.commands import Complete, CommandDefinition


class Command(CommandDefinition):
    """ Run a local shell command on your attacking machine """

    PROG = "local"
    ARGS = None
    LOCAL = True

    def run(self, manager: "pwncat.manager.Manager", args):
        subprocess.run(args, shell=True)
