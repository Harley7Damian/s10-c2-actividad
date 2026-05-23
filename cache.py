import hashlib
import os

import redis


REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL no esta configurada.")

r = redis.from_url(REDIS_URL, decode_responses=True)


def _key(prompt):
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return f"gemini-response:{digest}"


def get_cached_response(prompt):
    return r.get(_key(prompt))


def set_cached_response(prompt, response):
    r.set(_key(prompt), response, ex=3600)
