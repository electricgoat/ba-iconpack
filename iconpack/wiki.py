"""The calls deploy.py makes to bluearchive.wiki's API, through pywikiapi as in ../wiki-scripts/wiki.py."""
import time

import pywikiapi
import requests
from pywikiapi import ApiError

WIKI_API = 'https://bluearchive.wiki/w/api.php'
USER_AGENT = 'ba-iconpack deploy.py pywikiapi/4.3.0'
RETRY_DELAYS = [5, 15, 30, 60, 120]  # seconds before each retry of a request the wiki failed


class Site(pywikiapi.Site):
    """pywikiapi's Site, retrying requests the wiki fails (5xx, 429, dropped connections). Writes
    assert a login, so a lost session fails them rather than editing anonymously."""

    def __init__(self, url=WIKI_API):
        super().__init__(url, headers={'User-Agent': USER_AGENT})

    def request(self, *args, **kwargs):
        for delay in RETRY_DELAYS + [None]:
            try:
                return super().request(*args, **kwargs)
            except ApiError as error:  # 'Call failed', holding a response other than 200 OK
                response = error.data
                failure = f'HTTP {response.status_code} {response.reason}'
                if delay is None or response.status_code < 500 and response.status_code != 429:
                    raise requests.HTTPError(failure, response=response) from None
            except (requests.ConnectionError, requests.Timeout) as error:
                if delay is None:
                    raise
                failure = repr(error)
            print(f'Wiki request failed with {failure}, retrying in {delay} s')
            time.sleep(delay)

    def texts(self, titles):
        """Current text of each page, or None if it doesn't exist, keyed by the given titles."""
        result = self('query', titles=titles, prop='revisions', rvprop='content', rvslots='main')['query']
        normalized = {n['from']: n['to'] for n in result.get('normalized', [])}
        pages = {p['title']: p for p in result['pages']}
        texts = {}
        for title in titles:
            page = pages[normalized.get(title, title)]
            texts[title] = None if 'missing' in page else page['revisions'][0]['slots']['main']['content']
        return texts

    def file(self, name):
        """SHA-1 and URL of the file the wiki has under the name, or None."""
        page = self('query', titles=f'File:{name}', prop='imageinfo', iiprop='sha1|url')['query']['pages'][0]
        info = page.get('imageinfo')
        return {'sha1': info[0]['sha1'], 'url': info[0]['url']} if info else None

    def edit(self, title, text, summary):
        """Saves the page; returns whether that made a new revision."""
        result = self('edit', title=title, text=text, summary=summary, token=self.token(), POST=True,
                      **{'assert': 'user'})['edit']
        if result.get('result') != 'Success':
            raise ApiError('Edit failed', result)
        return 'nochange' not in result

    def upload(self, data, name, comment, text):
        """Uploads the file's bytes under the name, as a new version if the wiki has one; returns
        whether it did (False when the wiki's current version is the same)."""
        try:
            result = self('upload', filename=name, comment=comment, text=text, ignorewarnings=True,
                          token=self.token(), POST=True, EXTRAS={'files': {'file': (name, data)}},
                          **{'assert': 'user'})['upload']
        except ApiError as error:
            if isinstance(error.data, dict) and error.data.get('code') == 'fileexists-no-change':
                return False
            raise
        if result.get('result') != 'Success':
            raise ApiError('Upload failed', result)
        return True
