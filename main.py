# main
# Program entry point

import sys

import asyncio

from twitch_bot import client
from twitch_bot import log

sys.path.append('twitch_bot')


def main():

    irc_client = client.IRCClient()

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(irc_client.start(loop))
    loop.run_forever()


if __name__ == '__main__':
    main()
