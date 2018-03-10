# utils.py

import aiohttp
import logging
import os


LOG = logging.getLogger('debug')


def get_project_dir():
    return os.path.abspath(os.path.dirname(__file__))


def get_source_dirname():
    return os.path.basename(os.path.dirname(__file__))


def get_full_path(filename):
    return "{project_dir}/{filename}".format(project_dir=get_project_dir(), filename=filename)


async def request(url, headers):
    """ Asynchronously request an url.

    :param url: The url to request
    :param headers: HTTP headers to request with
    :return: request body
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                status_code = resp.status
                if status_code == 200:
                    return await resp.json()
                elif 400 < status_code < 500:
                    LOG.error("Bad request {url} ({status_code})".format(url=url, status_code=status_code))
                elif 500 < status_code < 600:
                    LOG.error("The request didn't succeed {url} ({status_code})".format(url=url, status_code=status_code))
    except aiohttp.client_exceptions.ClientError as e:
        LOG.error("An error has occured while requesting the url {url}".format(url=url))
