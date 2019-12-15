import asyncio
import logging
from dataclasses import dataclass
from typing import NoReturn

from deei import bootstrap, module, injectable


logger = logging.getLogger('example')
logging.basicConfig(level=logging.INFO, format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')
logging.getLogger('deei').setLevel(logging.DEBUG)


@injectable()
class HttpService:

    def __init__(self):
        import aiohttp
        self.session = aiohttp.ClientSession()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.session.close()


@module(providers=[HttpService])
class ApplicationServices:
    pass


@injectable()
@dataclass()
class GooglePinger:

    http_service: HttpService

    async def ping(self) -> bool:
        async with self.http_service.session.get('https://google.com') as response:
            return response.status == 200


@module(providers=[GooglePinger])
class DomainServices:
    pass


@module(imports=[ApplicationServices, DomainServices])
@dataclass()
class Application:

    google_pinger: GooglePinger

    async def run(self) -> NoReturn:
        for _ in range(3):
            logger.info('ping result: {}'.format(
                await self.google_pinger.ping()
            ))
            await asyncio.sleep(1)


async def main():
    async with bootstrap(Application) as app:
        await app.run()


if __name__ == '__main__':
    asyncio.run(main())
