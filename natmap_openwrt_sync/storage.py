import json
import aiofiles
from typing import Optional, TypedDict

from .config import config


class MappingValueT(TypedDict):
    ip: str
    port: int


# key is f"{protocol}:{inner_port}:"
MappingsT = dict[str, MappingValueT]


async def get_all_stored_mappings() -> MappingsT:
    try:
        async with aiofiles.open(config["storage_file"]) as f:
            return json.loads(await f.read())
    except FileNotFoundError:
        return {}


async def get_stored_mapping(key: str) -> MappingValueT:
    mappings = await get_all_stored_mappings()
    if key in mappings:
        return mappings[key]
    else:
        return {}


async def override_stored_mappings(mappings: MappingsT):
    async with aiofiles.open(config["storage_file"], "w") as f:
        await f.write(json.dumps(mappings))


async def update_stored_mapping(mappings: MappingsT):
    stored_mappings = await get_all_stored_mappings()
    stored_mappings.update(mappings)
    await override_stored_mappings(stored_mappings)
