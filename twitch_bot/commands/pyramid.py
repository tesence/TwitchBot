import logging

import cfg
from twitch_bot import irc

LOG = logging.getLogger('debug')


class Pyramid(irc.Command):
    """ Static class to build a pyramid. """

    MAX_SIZE = 5

    @staticmethod
    def _size_threshold(size):
        """ Threshold the pyramid size to avoid huge pyramids

        :param size: pyramid size set by the chatter
        :return: pyramid size after thresholding
        """
        return int(size) if int(size) < Pyramid.MAX_SIZE else Pyramid.MAX_SIZE

    def process(self):
        """ Build a pyramid based on input args

        :return: list of pyramid parts
        """
        size = cfg.DEFAULT_PYRAMID_SIZE
        symbol = cfg.DEFAULT_PYRAMID_SYMBOL

        if not len(self.args):
            pass
        elif len(self.args) == 1:
            if self.args[0].isdigit():
                size = Pyramid._size_threshold(self.args[0])
            else:
                symbol = self.args[0]
        elif len(self.args) == 2:
            symbol = self.args[0]
            if self.args[1].isdigit():
                size = Pyramid._size_threshold(self.args[1])

        LOG.debug("{author} has requested a pyramid with the args [{args}], "
                  "sending pyramid (symbol={symbol},size={size})"
                  .format(author=self.author, args=",".join(self.args), symbol=symbol, size=size))
        pyramid = []
        for i in range(2 * size - 1):
            block = [symbol] * (i + 1 if i < size else 2 * size - (i + 1))
            block = " ".join(block)
            pyramid.append(block)

        return pyramid
