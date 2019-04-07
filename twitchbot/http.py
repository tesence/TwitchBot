import abc
import asyncio
import collections
from datetime import datetime, timedelta
import hashlib
import hmac
import logging
import math
import sanic
from sanic import response
import socket
from urllib import parse

import aiohttp

from twitchbot import config


LOG = logging.getLogger(__name__)
CONF = config.CONF

TWITCH_API_URL = "https://api.twitch.tv/helix"
WEBHOOK_URL = f"{TWITCH_API_URL}/webhooks"


class RateBucket:

    def __init__(self, rate, per=60):
        self._tokens = rate
        self._rate = rate
        self._per = per
        self._reset_date = None

    async def consume(self):
        self._reset_date = self._reset_date or datetime.utcnow() + timedelta(seconds=self._per)

        if self._tokens > 0:
            self._tokens -= 1
        else:
            await self._reset()

    async def _reset(self):
        wait = math.ceil((self._reset_date - datetime.utcnow()).total_seconds())
        if wait > 0:
            await asyncio.sleep(wait)
        self._tokens = self._rate
        self._reset_date = None
        await self.consume()


class APIError(Exception):

    def __init__(self, message, original=None):
        self.message = message
        if original:
            self.message += f" - {original.message} ({original.status})"
        super().__init__(self.message)


class APIClientError(APIError):

    def __init__(self, original):
        message = "Invalid Request"
        super().__init__(message, original)


class APIServerError(APIError):

    def __init__(self, original):
        message = "Server Error"
        super().__init__(message, original)


class APIClient:

    def __init__(self, bucket=None, *args, **kwargs):
        self._session = aiohttp.ClientSession(*args, **kwargs, raise_for_status=True)
        self._bucket = bucket

    async def request(self, method, url, return_json=False, **kwargs):

        LOG.debug(f"Outgoing request: {method.upper()} {url} (params={kwargs})")
        if self._bucket:
            await self._bucket.consume()

        try:
            r = await self._session.request(method, url, **kwargs)
            return await r.json() if return_json else await r.text()
        except aiohttp.ClientResponseError as error:
            if 400 <= error.status < 500:
                output_error = APIClientError(error)
                LOG.error(output_error.message)
                raise output_error
            elif 500 <= error.status < 600:
                output_error = APIServerError(error)
                LOG.error(output_error.message)
                raise output_error
        except aiohttp.ClientError as error:
            output_error = APIError(str(error))
            LOG.error(output_error.message)
            raise output_error

    async def get(self, uri, return_json=False, **kwargs):
        return await self.request("get", uri, return_json=return_json, **kwargs)

    async def post(self, uri, data=None, return_json=False, **kwargs):
        return await self.request("post", uri, return_json=return_json, json=data, **kwargs)


class TokenSession(APIClient):

    def __init__(self, loop):
        super().__init__(loop=loop)
        self._token = None
        self._expires_at = None

    async def get_token(self):
        now = datetime.utcnow()
        need_refresh = True if not self._expires_at else now > self._expires_at

        if need_refresh:
            params = {
                'client_id': CONF.CLIENT_ID,
                'client_secret': CONF.CLIENT_SECRET,
                'grant_type': "client_credentials"
            }
            url = f"https://id.twitch.tv/oauth2/token?{parse.urlencode(params)}"
            token_data = await self.post(url, return_json=True)
            self._token = token_data['access_token']
            self._expires_at = now + timedelta(seconds=token_data['expires_in'])
            LOG.info(f"New token issued: {token_data['access_token']} (expires on {self._expires_at})")

        return self._token

    async def get_authorization_header(self):
        token = await self.get_token()
        return {'Authorization': f"Bearer {token}"}


def log_request(route):

    async def inner(server, request, *args, **kwargs):
        LOG.debug(f"Incoming request from '{request.ip}:{request.port}': "
                  f"'{request.method} http://{request.host}{request.path}' "
                  f"headers={request.headers}, args={request.args}, body={request.body}")
        return await route(server, request, *args, **kwargs)

    return inner


def verify_payload(route):
    """Decorator which verifies that a request was been sent from Twitch by comparing the 'X-Hub-Signature' header.

    code from https://gist.github.com/SnowyLuma/a9fb1c2707dc005fe88b874297fee79f"""

    async def inner(server, request, *args, **kwargs):
        secret = CONF.WEBHOOK_SECRET.encode('utf-8')
        digest = hmac.new(secret, msg=request.body, digestmod=hashlib.sha256).hexdigest()

        if hmac.compare_digest(digest, request.headers.get('X-Hub-Signature', '')[7:]):
            return await route(server, request, *args, **kwargs)

        LOG.warning("The hash for this notification is invalid")
        return sanic.response.text(None, status=403)

    return inner


def remove_duplicates(route):
    """Decorator which prevents duplicate notifications being processed more than once.

    code from: https://gist.github.com/SnowyLuma/a9fb1c2707dc005fe88b874297fee79f"""

    async def inner(server, request, *args, **kwargs):
        notification_id = request.headers.get('Twitch-Notification-ID')

        if notification_id in server._notification_ids:
            LOG.warning(f'Received duplicate notification with ID {notification_id}, discarding.')

            return sanic.response.text(None, status=204)

        result = await route(server, request, *args, **kwargs)
        server._notification_ids.append(notification_id)
        return result

    return inner


class TwitchWebhookServer(APIClient):

    def __init__(self, loop, callback):

        headers = {"Client-ID": CONF.CLIENT_ID}

        super().__init__(headers=headers, loop=loop, bucket=RateBucket(800, 60))
        self._token_session = TokenSession(loop)
        self._app = sanic.Sanic(configure_logging=False)
        self._app.add_route(self._handle_get, "<endpoint:[a-z/]*>", methods=['GET'])
        self._app.add_route(self._handle_post, "<endpoint:[a-z/]*>", methods=['POST'])
        self._host = socket.gethostbyname(socket.gethostname())
        self._port = CONF.WEBHOOK_PORT
        self._callback = callback
        self._external_host = None
        self._server = None

        self._topic_by_endpoint = {topic.ENDPOINT: topic for topic in Topic.__subclasses__()}

        # Store the 50 last notification ids to prevent duplicates
        self._notification_ids = collections.deque(maxlen=50)

        self._pending_subscriptions = {}
        self._pending_cancellation = {}

        loop.create_task(self._set_external_host())

    async def _set_external_host(self):
        if not self._external_host:
            external_ip = await self.get('https://api.ipify.org/')
            self._external_host = f"http://{external_ip}:{self._port}"
            LOG.info(f"External host: {self._external_host}")

    async def _get_webhook_action_params(self, mode, topic, duration=86400):
        data = {
            'hub.mode': mode,
            'hub.topic': topic.as_uri,
            'hub.callback': f"{self._external_host}{topic.ENDPOINT}?{parse.urlencode(topic.params)}",
            'hub.secret': CONF.WEBHOOK_SECRET
        }
        if mode == 'subscribe':
            data['hub.lease_seconds'] = duration

        return data

    async def list_subscriptions(self):
        headers = await self._token_session.get_authorization_header()
        body = await self.get(f"{WEBHOOK_URL}/subscriptions?first=100", return_json=True, headers=headers)
        return [Subscription.get_subscription(sub) for sub in body['data']]

    async def subscribe(self, *topics, duration=86400):
        headers = await self._token_session.get_authorization_header()

        tasks = {topic: self._subscribe(topic, duration, headers) for topic in topics}
        await asyncio.gather(*tasks.values())

        if not len(tasks) == len([task for task in tasks.values() if task]):
            LOG.warning(f"Subscriptions failed: {[topic for topic, task in tasks.items() if not task]}")

    async def _subscribe(self, topic, duration, headers):
        success = False

        data = await self._get_webhook_action_params('subscribe', topic, duration)
        self._pending_subscriptions[topic.as_uri] = asyncio.Event()
        await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)

        try:
            await asyncio.wait_for(self._pending_subscriptions[topic.as_uri].wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        else:
            success = True
        self._pending_subscriptions.pop(topic.as_uri)
        return success

    async def cancel(self, *topics):
        headers = await self._token_session.get_authorization_header()

        tasks = {topic: self._cancel(topic, headers) for topic in topics}
        await asyncio.gather(*tasks.values())

        if not len(tasks) == len([task for task in tasks.values() if task]):
            LOG.warning(f"Cancellations failed: {[topic for topic, task in tasks.items() if not task]}")

    async def _cancel(self, topic, headers):
        success = False

        data = await self._get_webhook_action_params('unsubscribe', topic)
        await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)
        self._pending_cancellation[topic.as_uri] = asyncio.Event()

        try:
            await asyncio.wait_for(self._pending_cancellation[topic.as_uri].wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        else:
            success = True
        self._pending_cancellation.pop(topic.as_uri)
        return success

    @log_request
    async def _handle_get(self, request, endpoint):
        topic = self._topic_by_endpoint[f"/{endpoint}"](**{k: request.args.get(k) for k in request.args})
        mode = request.args['hub.mode'][0]

        if mode == 'denied':
            LOG.warning(f"A subscription has been denied for topic: {topic}")
            return response.HTTPResponse(body='200: OK', status=200)

        if 'hub.challenge' in request.args:
            challenge = request.args['hub.challenge'][0]
            LOG.info(f"Challenge received: {challenge}")
            try:
                if mode == 'subscribe':
                    self._pending_subscriptions[topic.as_uri].set()
                elif mode == 'unsubscribe':
                    self._pending_cancellation[topic.as_uri].set()
            except KeyError:
                LOG.warning(f"A challenge has been received, {topic} but there is no pending action, "
                            f"the subscription might have been made externally")
            return response.HTTPResponse(body=challenge, headers={'Content-Type': 'application/json'})

    @log_request
    @verify_payload
    @remove_duplicates
    async def _handle_post(self, request, endpoint):
        topic = self._topic_by_endpoint[f"/{endpoint}"](**{k: request.args.get(k) for k in request.args})
        await self._callback(topic, request.json)
        return response.HTTPResponse(body='202: OK', status=202)

    async def start(self):
        try:
            self._server = await self._app.create_server(host=self._host, port=self._port)
            LOG.info(f"Webhook server listening on {self._host}:{self._port}")
        except OSError:
            LOG.exception("Cannot start the webhook server")

    def stop(self):
        LOG.debug(f"Stopping webhook server...")
        self._server.close()
        LOG.debug(f"Webhook server successfully stopped")


class Subscription:

    def __init__(self, topic, expires_at, callback):
        self.topic = topic
        self.expires_at = expires_at
        self.callback = callback

    def __repr__(self):
        return f"<{self.__class__.__name__} topic='{self.topic.as_uri}' expires_at='{self.expires_at}'' " \
            f"callback='{self.callback}'> "

    @property
    def expires_in(self):
        return (self.expires_at - datetime.now()).total_seconds()

    @classmethod
    def get_subscription(cls, sub):
        topic = Topic.get_topic(sub['topic'])
        expires_at = datetime.strptime(sub['expires_at'], "%Y-%m-%dT%H:%M:%SZ")
        callback = sub['callback']
        return cls(topic, expires_at, callback)


class Topic(abc.ABC):

    __slots__ = ()

    ENDPOINT = None

    def __init__(self, **kwargs):
        self.params = {slot: value for slot, value in kwargs.items() if slot in self.__slots__}

    def __repr__(self):
        return f"<{self.__class__.__name__} uri='{self.as_uri}'>"

    def __str__(self):
        return self.__repr__()

    def __hash__(self):
        return hash(str(self))

    @property
    def as_uri(self):
        return f"{TWITCH_API_URL}{self.ENDPOINT}?{parse.urlencode(self.params)}"

    @classmethod
    def get_topic(cls, url):
        parsed_url = parse.urlparse(url)
        topic_class = next((subclass for subclass in cls.__subclasses__()
                            if f"/helix{subclass.ENDPOINT}" == parsed_url.path), None)
        params = dict(parse.parse_qsl(parsed_url.query))
        return topic_class(**params)

    @property
    def id(self):
        return next((self.params.get(slot) for slot in self.__slots__ if self.params.get(slot) is not None), None)


class StreamChanged(Topic):

    __slots__ = ('user_id',)

    ENDPOINT = "/streams"


class UserFollows(Topic):

    __slots__ = ('from_id', 'to_id')

    ENDPOINT = "/users/follows"

    @property
    def as_uri(self):
        return f"{TWITCH_API_URL}{self.ENDPOINT}?first=1&{parse.urlencode(self.params)}"