import abc
import importlib
import logging
import re

import cfg
from twitch_bot import exception
from twitch_bot import utils

LOG = logging.getLogger('debug')


class Command(abc.ABC):

    COMMAND_RE = "^!(\w+)(.*)"

    VALID_COMMANDS = {}
    BANNED_PREFIX = ["!", ".", "/"]

    def __init__(self, author, command, args):
        self.author = author
        self.command = command
        self.args = args

    @staticmethod
    async def load_commands():
        """ Load all the IRC commands """
        source_dirname = utils.get_source_dirname()
        commands_dirname = "commands"
        for command in cfg.VALID_COMMANDS:
            module_name = source_dirname + "." + commands_dirname + "." + command
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                LOG.error("Cannot find module: {module_name}".format(module_name=command))
        Command.VALID_COMMANDS = {c.__name__.lower(): c for c in Command.__subclasses__()}
        LOG.debug("Commands loaded: {commands}".format(commands=list(Command.VALID_COMMANDS)))

    @staticmethod
    def is_command(message):
        """ Check if the message is a command

        :param message: original message
        :return: True if the message is  a command, False otherwise
        """
        return True if re.match(Command.COMMAND_RE, message.content) else False

    @staticmethod
    def get_command(message):
        """ Return the requested command object to be processed.

        :param message: original message
        :return: Command object
        """
        matched = re.match(Command.COMMAND_RE, message.content)
        command = matched.group(1)
        args = matched.group(2).split()
        for arg in args:
            if arg[0] in Command.BANNED_PREFIX:
                raise exception.WrongArgumentException
        try:
            command_class = Command.VALID_COMMANDS[command]
            return command_class(message.author, command, args)
        except KeyError:
            LOG.error("Unknown command '{command}'".format(command=command))
            raise exception.UnknownCommandException

    @abc.abstractmethod
    def process(self):
        """ Process the command """
