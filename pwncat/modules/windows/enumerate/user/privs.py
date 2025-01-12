#!/usr/bin/env python3
import dataclasses
from enum import IntFlag

from rich.table import Table
from pwncat.facts import Fact
from pwncat.platform.windows import Windows
from pwncat.modules.enumerate import Schedule, EnumerateModule


class LuidAttributes(IntFlag):

    DISABLED = 0x00
    SE_PRIVILEGE_ENABLED_BY_DEFAULT = 0x01
    SE_PRIVILEGE_ENABLED = 0x02
    SE_PRIVILEGE_REMOVE = 0x04
    SE_PRIVILEGE_USED_FOR_ACCESS = 0x80000000


class TokenPrivilegeData(Fact):
    def __init__(
        self,
        source: str,
        privilege: str,
        attributes: LuidAttributes,
        token_handle: int,
        pid: int,
    ):
        super().__init__(source=source, types=["user.privs"])

        self.privilege: str = privilege
        self.attributes: LuidAttributes = attributes
        # self.token_handle: int = token_handle
        # self.pid: int = pid

    def title(self, session: "pwncat.manager.Session"):

        if self.attributes == LuidAttributes.DISABLED:
            color = "red"
        else:
            color = "green"

        attrs = str(self.attributes)
        attrs = attrs.replace("LuidAttributes.", "")
        attrs = attrs.replace("|", "[/cyan]|[cyan]")
        attrs = "[cyan]" + attrs + "[/cyan]"

        return f"[{color}]{self.privilege}[/{color}] -> {attrs}"


class Module(EnumerateModule):
    """Enumerate user privileges using PowerView's Get-ProcessTokenPrivilege"""

    PROVIDES = ["user.privs"]
    PLATFORM = [Windows]
    SCHEDULE = Schedule.ALWAYS

    def enumerate(self, session: "pwncat.manager.Session"):

        # Ensure that powerview is loaded
        session.run(
            "manage.powershell.import",
            path="PowerShellMafia/PowerSploit/Privesc/PowerUp.ps1",
        )

        # Grab our current token privileges
        results = session.platform.powershell("Get-ProcessTokenPrivilege")
        if len(results) == 0:
            session.log("[red]error[/red]: Get-ProcessTokenPrivilege failed")
            return

        # They end up in an array in an array
        privs = results[0]

        # Create our enumeration data types
        for priv in privs:
            yield TokenPrivilegeData(
                source=self.name,
                privilege=priv["Privilege"],
                attributes=LuidAttributes(priv["Attributes"]),
                token_handle=priv["TokenHandle"],
                pid=priv["ProcessId"],
            )
