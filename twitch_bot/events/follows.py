import asyncio
import iso8601
import logging

import cfg
from twitch_bot import utils
from twitch_bot.events import base

LOG = logging.getLogger('debug')


class Follows(base.Event):

    id = None

    follows = []

    @staticmethod
    def _format_follower_list(follower_list):
        follower_list = [f['name'] for f in follower_list]
        if len(follower_list) == 1:
            return follower_list[0]
        else:
            return ", ".join(follower_list[:-1]) + " and " + follower_list[-1]

    @staticmethod
    async def _get_id():
        url = "{twitch_api_url}/users?login={channel_name}"\
              .format(twitch_api_url=cfg.TWITCH_API_URL, channel_name=cfg.TWITCH_IRC_CHANNEL)
        try:
            body = await utils.request(url, headers=Follows.HEADERS)
            channel_id = body['users'][0]['_id']
        except (KeyError, TypeError) as e:
            LOG.error("Cannot parse retrieved id for {channel_name} ({message})"
                      .format(channel_name=cfg.TWITCH_IRC_CHANNEL, message=e.args))
        else:
            LOG.debug("API data for {channel_name}: {data} ({url})"
                      .format(channel_name=cfg.TWITCH_IRC_CHANNEL, data=body['users'], url=url))

            Follows.id = channel_id

    @staticmethod
    async def _get_follows():
        url = "{twitch_api_url}/channels/{id}/follows" \
            .format(twitch_api_url=cfg.TWITCH_API_URL, id=Follows.id)
        try:
            body = await utils.request(url, headers=Follows.HEADERS)
            follows = [
                {
                    'name': follow['user']['display_name'],
                    'date': follow['created_at']
                }
                for follow in body['follows']
            ]
        except (KeyError, TypeError) as e:
            LOG.error("Cannot parse retrieved followers for {channel_name} ({message})"
                      .format(channel_name=cfg.TWITCH_IRC_CHANNEL, message=e.args))
        else:
            LOG.debug("API data for {channel_name}: {data} ({url})"
                      .format(channel_name=cfg.TWITCH_IRC_CHANNEL, data=body, url=url))
            return follows

    @staticmethod
    async def listen(irc_client):
        while True:
            if not Follows.id:
                await Follows._get_id()
            follows = await Follows._get_follows()
            if follows is not None:
                new_follows = [f for f in follows
                               if iso8601.parse_date(f['date']) > Follows.INIT_DATE and
                               f not in Follows.follows]
                if new_follows:
                    LOG.debug("New follows found: %s", new_follows)
                    new_follows_string = Follows._format_follower_list(new_follows)
                    await irc_client.send_message("/me " + cfg.FOLLOW_MESSAGE.format(new_follows_string))
                    Follows.follows = follows

            await asyncio.sleep(10)
