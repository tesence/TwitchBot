import asyncio
import logging

from twitchio.ext import commands
from twitchio import errors

from twitchbot import config
from twitchbot import http

LOG = logging.getLogger(__name__)
CONF = config.CONF


class Bot(commands.Bot):

    def __init__(self):
        super().__init__(irc_token=CONF.IRC_TOKEN, client_id=CONF.CLIENT_ID, nick=CONF.BOT_USERNAME,
                         prefix=CONF.PREFIX, initial_channels=CONF.CHANNELS)
        self._webhook_server = http.TwitchWebhookServer(self.loop, self.on_webhook_event)
        self._id_by_login = {}

        def task_done_callback(fut):
            if fut.cancelled():
                LOG.debug(f"The task has been cancelled: {fut}")
                return
            error = fut.exception()
            if error:
                LOG.error(f"A task ended unexpectedly: {fut}", exc_info=(type(error), error, error.__traceback__))

        webhook_task = self.loop.create_task(self._webhook_server.start())
        webhook_task.add_done_callback(task_done_callback)

        update_task = self.loop.create_task(self._update_subscription())
        update_task.add_done_callback(task_done_callback)

    async def event_ready(self):
        LOG.info(f"Successfully logged in as '{CONF.BOT_USERNAME}' in channels: {self.initial_channels}")

    async def _update_subscription(self):
        while True:
            try:
                for login in self.initial_channels:
                    if login not in self._id_by_login:
                        self._id_by_login[login] = (await self.get_users(login))[0].id

                subscriptions = await self._webhook_server.list_subscriptions()

                user_ids = [sub.topic.id for sub in subscriptions]

                ids_to_resub = set(self._id_by_login.values()) - set(user_ids)
                if ids_to_resub:
                    await self._webhook_server.subscribe(*[http.UserFollows(to_id=user_id) for user_id in ids_to_resub])
                await asyncio.sleep(600)
            except errors.HTTPException:
                await asyncio.sleep(10)

    async def on_webhook_event(self, topic, body):
        follower_name = body['data'][0]['from_name']
        streamer_name = body['data'][0]['to_name']
        LOG.info(f"New follower: '{follower_name}'")
        await self.get_channel(streamer_name.lower()).send(f"Thank you {follower_name} for the follow oriHug")
