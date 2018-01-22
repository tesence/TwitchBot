import asyncio
import itertools
import logging
import socket

import cfg

from twitch_bot import exception
from twitch_bot.irc import Message
from twitch_bot.commands.base import Command
from twitch_bot import utils

LOG = logging.getLogger('debug')


class IRCClient(object):
    """ Client to interact with the chat. """

    CHAT_URL = "https://tmi.twitch.tv/group/user/{user}/chatters".format(user=cfg.CHAN.lower())

    def __init__(self):
        self._socket = socket.socket()
        self._mod_list = {}

    # BOT COMMANDS #

    def _connect(self):
        """ Connect to the channel. """
        self._socket.connect((cfg.HOST, cfg.PORT))
        self._socket.send(bytes("PASS {password}\r\n".format(password=cfg.PASS), "utf-8"))
        self._socket.send(bytes("NICK {nickname}\r\n".format(nickname=cfg.NICK), "utf-8"))
        self._socket.send(bytes("JOIN #{channel}\r\n".format(channel=cfg.CHAN), "utf-8"))
        LOG.debug("Client connected to {channel_name}".format(channel_name=cfg.CHAN))

    async def start(self, loop):
        """ Start all the underlying tasks """

        self._connect()

        # Load all the resources
        tasks = [
            Command.load_commands(),
        ]
        await asyncio.gather(*tasks)

        # Run the main tasks
        asyncio.ensure_future(self._fill_mod_list())
        asyncio.ensure_future(loop.run_in_executor(None, self._listen))

    def send(self, message):
        """ Send a message to the server.
        :param message: the message to send
        """
        self._socket.send(bytes("{message}\r\n".format(message=message), "utf-8"))

    def send_message(self, message):
        """ Send a private message to the server.
        :param message: the message to send
        """
        self.send("PRIVMSG #{channel} :{message}".format(channel=cfg.CHAN, message=message))

    def ban(self, user):
        """ Ban a user from the channel.
        :param user: The user to ban
        """
        self.send_message(".ban {user}".format(user=user))
        LOG.debug("%s has been banned", user)

    def timeout(self, user, seconds=600):
        """ Ban a user from the channel.
        :param user: The user to ban
        :param seconds: the length of the timeout in seconds (default 600)
        """
        self.send_message(".timeout {user} {seconds}".format(user=user, seconds=seconds))
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

    def _listen(self):
        """ Keep reading in the socket for new messages. """
        while True:
            received = self._socket.recv(1024).decode("utf-8").rstrip()
            if not len(received) == 0:
                self._handle_message(received)
            else:
                LOG.error("The bot has been disconnected, reconnecting...")
                self._connect()

    def _handle_message(self, bytes):
        """ Check for private messages and commands

        :param bytes: byte sequence
        """
        raw_messages = bytes.split('\n')
        for raw_message in raw_messages:
            if Message.is_ping(raw_message):
                self.send(Message.PONG)
            elif Message.is_message(raw_message):
                message = Message(raw_message)
                if Command.is_command(message):
                    try:
                        command = Command.get_command(message)
                        command_result = command.process()
                        for part in command_result:
                            self.send_message(part)
                    except (exception.UnknownCommandException,
                            exception.WrongArgumentException):
                        pass
