import asyncio
import json
import logging

from aiohttp import web

from .config import config
from .ssh import SSHClient
from .storage import Database, MappingsT

class DuplicateFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        current_log = (record.module, record.levelno, record.msg)
        if current_log != getattr(self, "last_log", None):
            self.last_log = current_log
            return True
        return False

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=config["logging_level"],
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()
logger.addFilter(DuplicateFilter())
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


routes = web.RouteTableDef()

ws_clients: set[web.WebSocketResponse] = set()
db = Database()


async def notify_clients(mappings: dict):
    logging.debug(f"notifying clients...")
    for ws in ws_clients:
        if ws.closed:
            continue
        try:
            await ws.send_json(mappings)
        except Exception:
            pass


@routes.get("/all_mappings")
async def get_all_mappings(request: web.Request):
    logging.debug(f"Client {request.remote} requested all mappings")
    return web.json_response(await db.get_all_mappings())


@routes.get("/mapping/{key}")
async def get_mapping(request: web.Request):
    key = request.match_info["key"]
    logging.debug(f"Client {request.remote} requested mapping for {key}")
    mapping_info = await db.get_mapping(key)
    if mapping_info:
        return web.json_response(mapping_info)
    else:
        return web.Response(status=404)


@routes.put("/mappings")
async def update_mappings(request: web.Request):
    new_mappings = await request.json()
    logging.info(
        f"Client {request.remote} overrided mappings with value {new_mappings}"
    )
    asyncio.create_task(db.update_mappings(new_mappings))
    asyncio.create_task(notify_clients(new_mappings))

    return web.Response(status=204)


# this is used for notifying the client that the maps have changed
@routes.get("/ws")
async def websocket_handler(request: web.Request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logging.info(f"ws connection from {request.remote} open")
    ws_clients.add(ws)

    async for msg in ws:
        # we ignore all other messages
        if msg.type == web.WSMsgType.ERROR:
            logging.info(f"ws connection closed with exception {ws.exception()}")

    logging.info(f"ws connection from {request.remote} closed")
    ws_clients.remove(ws)

    return ws


async def ssh_monitor(ssh_client: SSHClient, poll_interval: int):
    while True:
        try:
            await ssh_client.ensure_connection()
            # list the files in /var/run/natmap/ and cat them to get the mappings
            raw_list = await ssh_client.run_command(
                "find /var/run/natmap/ -name \"*.json\" -exec cat '{}' +"
            )
        except Exception as e:
            logging.warning(f"ssh monitoring failed with exception {e}")

        # convert the raw list to a dict that's of type MappingsT
        mappings: MappingsT = dict()
        for raw_mapping in raw_list.strip().split("\n"):
            if not raw_mapping:
                continue
            mapping = json.loads(raw_mapping)
            mappings[f"{mapping['protocol']}:{mapping['inner_port']}"] = {
                "ip": mapping["ip"],
                "port": mapping["port"],
            }

        # if mappings changed, update the stored mappings and notify clients
        current_mappings = await db.get_all_mappings()
        if mappings != current_mappings:
            logging.info(f"mappings changed via ssh monitoring: {mappings}")
            await db.override_all_mappings(mappings)

            # only notify clients of new or updated mappings
            diff_mappings: MappingsT = dict()
            for key in mappings:
                if (
                    key not in current_mappings
                    or mappings[key] != current_mappings[key]
                ):
                    diff_mappings[key] = mappings[key]

            # when there is only mapping being removed, the diff_mappings will be empty
            if diff_mappings:
                await notify_clients(diff_mappings)

        await asyncio.sleep(poll_interval)


async def run():
    await db.connect(config["db_path"])

    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config["bind_host"], config["bind_port"])
    await site.start()

    ssh_config = config["ssh_monitor"]
    if ssh_config["enabled"]:
        ssh_client = SSHClient(
            host=ssh_config["ssh_host"],
            user=ssh_config["ssh_user"],
            port=ssh_config["ssh_port"],
            key_path=ssh_config["ssh_key_path"],
        )
        await ssh_client.ensure_connection()
        await ssh_monitor(ssh_client, ssh_config["ssh_poll_interval"])
        await ssh_client.close_connection()

    # await forever incase ssh monitoring is disabled
    await asyncio.Future()

    await db.close()


if __name__ == "__main__":
    asyncio.run(run())
