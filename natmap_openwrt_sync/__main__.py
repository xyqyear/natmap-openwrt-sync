import asyncio
import json
import logging

from aiohttp import web

from .config import config
from .ssh import SSHClient
from .storage import (
    MappingsT,
    get_all_stored_mappings,
    override_stored_mappings,
    update_stored_mapping,
    get_stored_mapping,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=config["logging_level"],
    datefmt="%Y-%m-%d %H:%M:%S",
)


routes = web.RouteTableDef()

ws_clients: set[web.WebSocketResponse] = set()


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
    logging.debug(f"Client {request.remote} requested all maps")
    return web.json_response(await get_all_stored_mappings())


@routes.get("/mapping/{key}")
async def get_mapping(request: web.Request):
    key = request.match_info["key"]
    logging.debug(f"Client {request.remote} requested map {key}")
    mapping_info = await get_stored_mapping(key)
    if mapping_info:
        return web.json_response(await get_stored_mapping(key))
    else:
        return web.Response(status=404)


@routes.put("/mappings")
async def update_mappings(request: web.Request):
    new_mappings = await request.json()
    logging.info(
        f"Client {request.remote} overrided mappings with value {new_mappings}"
    )
    asyncio.create_task(update_stored_mapping(new_mappings))
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


async def ssh_monitor():
    ssh_config = config["ssh_monitor"]
    if not ssh_config["enabled"]:
        return
    ssh_client = SSHClient(
        host=ssh_config["ssh_host"],
        user=ssh_config["ssh_user"],
        port=ssh_config["ssh_port"],
        key_path=ssh_config["ssh_key_path"],
    )
    await ssh_client.ensure_connection()
    while True:
        try:
            # list the files in /var/run/natmap/ and cat them to get the mappings
            raw_list = await ssh_client.run_command(
                "find /var/run/natmap/ -name \"*.json\" -exec cat '{}' +"
            )
        except Exception as e:
            logging.debug(f"ssh monitoring failed with exception {e}")

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
        current_mappings = await get_all_stored_mappings()
        if mappings != current_mappings:
            logging.info(f"mappings changed via ssh monitoring: {mappings}")
            await override_stored_mappings(mappings)

            # only notify clients of new or updated mappings
            diff_mappings: MappingsT = dict()
            for key in mappings:
                if (
                    key not in current_mappings
                    or mappings[key] != current_mappings[key]
                ):
                    diff_mappings[key] = mappings[key]
            await notify_clients(diff_mappings)

        await asyncio.sleep(ssh_config["ssh_poll_interval"])


async def run():
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config["bind_host"], config["bind_port"])
    await site.start()

    await ssh_monitor()

    # await forever incase ssh monitoring is disabled
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run())
