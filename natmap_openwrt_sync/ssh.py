from fabric import Connection
import asyncio
from .utils import aioify


class SSHClient:
    def __init__(self, host, user, port, key_path=None, connect_timeout=5) -> None:
        if key_path:
            connect_kwargs = {"key_filename": key_path}
        self.connection = Connection(
            host=host,
            user=user,
            port=port,
            connect_kwargs=connect_kwargs,
            connect_timeout=connect_timeout,
        )

    @aioify
    def open_connection(self):
        """
        may raise exceptions
        the caller should handle them
        """
        self.connection.open()
        self.connection.transport.set_keepalive(60)

    @aioify
    def close_connection(self):
        self.connection.close()

    async def ensure_connection(self, retry_interval=5):
        if self.connection.is_connected:
            return

        while True:
            try:
                await self.open_connection()
            except Exception:
                pass
            if self.connection.is_connected:
                break
            await asyncio.sleep(retry_interval)

    @aioify
    def run_command(self, command: str, timeout=5) -> str:
        """
        :raises Exception: If connection is not open
        may raise other exceptions raised by fabric.Connection.run
        the caller should handle them
        """
        if not self.connection.is_connected:
            raise Exception("Connection is not open")
        result = self.connection.run(command, hide=True, timeout=timeout)
        return result.stdout
