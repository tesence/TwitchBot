import asyncio

from twitchbot.bot import Bot


if __name__ == "__main__":

    loop = asyncio.get_event_loop()
    loop.create_task(Bot().start())
    loop.run_forever()
