from typing import TypedDict

import aiosqlite


class MappingValueT(TypedDict):
    ip: str
    port: int


# key is f"{protocol}:{inner_port}:"
MappingsT = dict[str, MappingValueT]


class Database:
    async def connect(self, db_path: str):
        self._db = await aiosqlite.connect(db_path)
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS mappings (key TEXT PRIMARY KEY, ip TEXT, port INTEGER)"
        )

    async def close(self):
        await self._db.close()

    async def get_all_mappings(self) -> MappingsT:
        async with self._db.execute("SELECT * FROM mappings") as cursor:
            mappings = await cursor.fetchall()
        return {key: {"ip": ip, "port": port} for key, ip, port in mappings}

    async def get_mapping(self, key: str) -> MappingValueT:
        async with self._db.execute(
            "SELECT * FROM mappings WHERE key=?", (key,)
        ) as cursor:
            mapping = await cursor.fetchone()
        if mapping:
            return {"ip": mapping[1], "port": mapping[2]}
        else:
            return {}

    async def update_mappings(self, mappings: MappingsT):
        await self._db.executemany(
            "INSERT OR REPLACE INTO mappings VALUES (?, ?, ?)",
            [
                (key, mapping["ip"], mapping["port"])
                for key, mapping in mappings.items()
            ],
        )
        await self._db.commit()

    async def override_all_mappings(self, mappings: MappingsT):
        await self._db.execute("DELETE FROM mappings")
        await self._db.commit()
        await self.update_mappings(mappings)
