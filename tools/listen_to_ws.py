import asyncio
import aiohttp


async def main():
    session = aiohttp.ClientSession()
    while True:
        async with session.ws_connect("http://localhost:8080/ws") as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(msg.data)
        
        await asyncio.sleep(5)


asyncio.run(main())
