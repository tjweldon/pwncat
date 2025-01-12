"""
Connect to a listening target server. This is slightly counter intuitive.
In this case, we are referring to connecting from the attacker perspective.
The victim would have received a bind shell payload, and is listening for
connection on a known port.

The only required arguments are ``host`` and ``port``.
"""
import os
import errno
import fcntl
import socket
from typing import Optional

from rich.progress import Progress, BarColumn

from pwncat.util import console
from pwncat.channel import Channel, ChannelError, ChannelClosed
from pwncat.channel.socket import Socket


class Connect(Socket):
    """
    Implements a channel which rides over a shell attached
    directly to a socket. This channel will connect to a
    target at the specified host and port, and assume a shell is connected.
    """

    def __init__(self, host: str, port: int, **kwargs):
        if not host:
            raise ChannelError("no host address provided")

        if port is None:
            raise ChannelError("no port provided")

        with Progress(
            f"connecting to [blue]{host}[/blue]:[cyan]{port}[/cyan]",
            BarColumn(bar_width=None),
            transient=True,
            console=console,
        ) as progress:
            task_id = progress.add_task("connecting", total=1, start=False)
            # Connect to the remote host
            client = socket.create_connection((host, port))

            progress.log(
                f"connection to "
                f"[blue]{host}[/blue]:[cyan]{port}[/cyan] [green]established[/green]"
            )

        super().__init__(client=client, host=host, port=port, **kwargs)
