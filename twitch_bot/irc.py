import logging
import re

LOG = logging.getLogger('debug')


class Message(object):

    MESSAGE_RE = ":(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :(.*)"
    PING = "PING :tmi.twitch.tv"
    PONG = "PONG :tmi.twitch.tv"

    def __init__(self, byte):
        matched = re.match(Message.MESSAGE_RE, byte)
        self.author = matched.group(1)
        self.content = matched.group(2)

    def __repr__(self):
        return "<%s:%s>" % (self.author, self.content)

    @staticmethod
    def is_message(byte):
        """ Check if a byte sequence is a private message

        :param byte: byte sequence
        :return: True if the byte sequence is a private message, False otherwise
        """
        return True if re.match(Message.MESSAGE_RE, byte) else False

    @staticmethod
    def is_ping(byte):
        """ Check if a byte sequence is a ping

        :param byte: byte sequence
        :return: True if the byte sequence is a ping, False otherwise
        """
        return byte == Message.PING
