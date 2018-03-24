import asyncio
import itertools
import logging

import cfg
from twitch_bot import exception
from twitch_bot.irc import Message
from twitch_bot.commands.base import Command
from twitch_bot.events.base import Event
from twitch_bot import utils

LOG = logging.getLogger('debug')


class IRCClient(object):
    """ Client to interact with the chat. """

    CHAT_URL = "https://tmi.twitch.tv/group/user/{user}/chatters".format(user=cfg.TWITCH_IRC_CHANNEL.lower())

    def __init__(self):
        self._mod_list = {}

    # BOT COMMANDS #

    async def _connect(self, loop):
        """ Connect to the channel. """
        connection = await asyncio.open_connection(host=cfg.TWITCH_IRC_HOST, port=cfg.TWITCH_IRC_PORT, loop=loop)
        self.reader, self.writer = connection
        self.writer.write(bytes("PASS {password}\r\n".format(password=cfg.TWITCH_IRC_PASSWORD), "utf-8"))
        self.writer.write(bytes("NICK {nickname}\r\n".format(nickname=cfg.TWITCH_IRC_BOTNAME), "utf-8"))
        self.writer.write(bytes("JOIN #{channel}\r\n".format(channel=cfg.TWITCH_IRC_CHANNEL), "utf-8"))
        LOG.debug("Client connected to {channel_name}".format(channel_name=cfg.TWITCH_IRC_CHANNEL))

    async def start(self, loop):
        """ Start all the underlying tasks """

        await self._connect(loop)

        # Load all the resources
        tasks = [
            Command.load_commands(),
            Event.load_events(self),
            self._fill_mod_list(),
            self._listen(loop)
        ]
        await asyncio.gather(*tasks)

    async def send(self, message):
        """ Send a message to the server.
        :param message: the message to send
        """
        self.writer.write(bytes("{message}\r\n".format(message=message), "utf-8"))

    async def send_message(self, message):
        """ Send a private message to the server.
        :param message: the message to send
        """
        await self.send("PRIVMSG #{channel} :{message}".format(channel=cfg.TWITCH_IRC_CHANNEL, message=message))

    async def ban(self, user):
        """ Ban a user from the channel.
        :param user: The user to ban
        """
        await self.send_message(".ban {user}".format(user=user))
        LOG.debug("%s has been banned", user)

    async def timeout(self, user, seconds=600):
        """ Ban a user from the channel.
        :param user: The user to ban
        :param seconds: the length of the timeout in seconds (default 600)
        """
        await self.send_message(".timeout {user} {seconds}".format(user=user, seconds=seconds))
        LOG.debug("%s has been timed out for %ss", user, seconds)

    def _is_mod(self, username):
        """ Return True if the user is a moderator
        :param username: the username to check
        :return: True if the user is a moderator, False otherwise
        """
        return username in itertools.chain(self._mod_list.values())

    async def _fill_mod_list(self):
        """ Fill the only moderators list periodically (every 10s). """
        while True:
            try:
                body = await utils.request(url=IRCClient.CHAT_URL, headers={"accept": "*/*"})
                self._mod_list = {rank: body['chatters'][rank]
                                  for rank in ["moderators", "global_mods", "admins", "staff"]}
            except KeyError:
                LOG.warning("Cannot retrieve stream chatters information (empty body)",)
            except (ValueError, TypeError):
                LOG.warning("Cannot retrieve stream chatters information")
            await asyncio.sleep(10)

    async def _listen(self, loop):
        """ Keep reading in the socket for new messages. """
        while True:
            received = (await self.reader.read(1024)).decode("utf-8").rstrip()
            if not len(received) == 0:
                await self._handle_message(received)
            else:
                LOG.error("The bot has been disconnected, reconnecting...")
                await self._connect(loop)

    async def _handle_message(self, bytes):
        """ Check for private messages and commands

        :param bytes: byte sequence
        """
        raw_messages = bytes.split('\n')
        for raw_message in raw_messages:
            if Message.is_ping(raw_message):
                await self.send(Message.PONG)
            elif Message.is_message(raw_message):
                message = Message(raw_message)
                if Command.is_command(message):
                    try:
                        command = Command.get_command(message)
                        command_result = command.process()
                        for part in command_result:
                            await self.send_message(part)
                    except (exception.UnknownCommandException,
                            exception.WrongArgumentException):
                        pass
