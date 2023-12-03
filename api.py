import asyncio
import json
import time
from functools import wraps

import aiohttp

import settings


HEADERS = {
    'Authorization': 'Bearer ' + settings.DMOJ_API_KEY
}
session = None


def join(*url_parts):
    return '/'.join(url_parts)


NEXT_REQUEST_TIME = {key: 0 for key in settings.DMOJ_REQUEST_DELAY.keys()}


async def make_request(url, ratelimit_key='default'):
    global NEXT_REQUEST_TIME
    global session
    if session is None:
        session = aiohttp.ClientSession(headers=HEADERS)
    delay = settings.DMOJ_REQUEST_DELAY[ratelimit_key]
    while NEXT_REQUEST_TIME[ratelimit_key] > time.time():
        await asyncio.sleep(NEXT_REQUEST_TIME[ratelimit_key] - time.time() + 0.01)
    NEXT_REQUEST_TIME[ratelimit_key] = time.time() + delay
    try:
        async with session.get(join(settings.DMOJ_BASE_URL, url)) as response:
            response.text = await response.text()
            return response
    except Exception:
        import traceback
        traceback.print_exc()
        return None


async def load_json(url, **kwargs):
    response = await make_request(url, **kwargs)
    if response is None or response.status != 200:
        return None
    return json.loads(response.text)


def single_object(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        data = await f(*args, **kwargs)
        if data is None:
            return data
        return data['data']['object']
    return wrapper


def multiple_object(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        page = 1
        objs = []
        while True:
            data = await f(*args, **kwargs, page=page)
            if data is None:
                break
            objs.extend(data['data']['objects'])
            if not data['data']['has_more']:
                break
            page += 1
        return objs
    return wrapper


@single_object
async def get_user(username):
    return await load_json(join(settings.DMOJ_API_URL, 'user', username))


async def get_user_about(username):
    return await make_request(join('user', username))


@multiple_object
async def get_users(page):
    print('get users', page)
    return await load_json(join(settings.DMOJ_API_URL, f'users?page={page}'), ratelimit_key='long')


@single_object
async def get_contest(key):
    return await load_json(join(settings.DMOJ_API_URL, 'contest', key))
