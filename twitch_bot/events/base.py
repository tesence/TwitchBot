import abc
import asyncio
from datetime import datetime
import importlib
import iso8601
import logging

import cfg
from twitch_bot import utils

LOG = logging.getLogger('debug')


class Event(abc.ABC):

    HEADERS = {
        "Client-ID": cfg.TWITCH_API_CLIENT_ID,
        "accept": cfg.TWITCH_API_ACCEPT
    }

    INIT_DATE = datetime.utcnow().replace(tzinfo=iso8601.UTC)

    VALID_EVENTS = {}

    @staticmethod
    async def load_events(irc_client):
        """ Load all the IRC commands """
        source_dirname = utils.get_source_dirname()
        events_dirname = "events"
        for event in cfg.VALID_EVENTS:
            module_name = source_dirname + "." + events_dirname + "." + event
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                LOG.error("Cannot find module: {module_name}".format(module_name=event))
        Event.VALID_EVENTS = {c.__name__.lower(): c for c in Event.__subclasses__()}
        for event in Event.VALID_EVENTS.values():
                asyncio.ensure_future(event.listen(irc_client))
        LOG.debug("Events loaded: {events}".format(events=list(Event.VALID_EVENTS)))

    @staticmethod
    @abc.abstractmethod
    async def listen(irc_client):
        """ """
