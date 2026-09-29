import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urljoin, urlparse


def origin(url):
    parsed = urlparse(url)
    return parsed.scheme.lower(), parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)


def safe_headers(client, url, headers):
    trusted = {
        origin('https://api.bookmate.yandex.net'),
        origin('https://api-gateway.bookmate.yandex.net'),
    }
    for attribute in ('base_url', 'graphql_url'):
        configured = getattr(client, attribute, None)
        if configured:
            trusted.add(origin(configured))
    if origin(url) not in trusted:
        return {key: value for key, value in headers.items() if key.lower() != 'auth-token'}
    return dict(headers)


def redirect_request(status, method, url, location, kwargs, headers):
    destination = urljoin(url, location)
    kwargs.pop('params', None)
    if origin(destination) != origin(url):
        headers = {key: value for key, value in headers.items()
                   if key.lower() not in ('authorization', 'cookie', 'proxy-authorization')}
    if (status == 303 and method != 'HEAD') or (status in (301, 302) and method == 'POST'):
        method = 'GET'
        kwargs.pop('data', None)
        kwargs.pop('json', None)
        headers = {key: value for key, value in headers.items()
                   if key.lower() not in ('content-type', 'content-length')}
    return destination, method, headers


@contextmanager
def atomic_download(filepath):
    destination = Path(filepath)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{destination.name}.', suffix='.part', dir=destination.parent)
    os.close(fd)
    try:
        yield temporary
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
