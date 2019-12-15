import asyncio
from typing import NoReturn
from deei import bootstrap


class ValueService:

    @staticmethod
    def get_value() -> str:
        return 'four'


class TimeoutService:

    value_service: ValueService

    def get_timeout(self):
        base_timeout = 1
        additional_timeout = len(self.value_service.get_value()) / 10
        return base_timeout + additional_timeout


class HttpService:

    def __init__(self):
        import aiohttp
        self.session = aiohttp.ClientSession()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.session.close()


class Application:

    value_service: ValueService
    timeout_service: TimeoutService
    http_service: HttpService

    async def run(self) -> NoReturn:
        for _ in range(3):
            print('value:', self.value_service.get_value())
            print('timeout:', self.timeout_service.get_timeout())
            await asyncio.sleep(self.timeout_service.get_timeout())


async def main():
    async with bootstrap(Application) as app:
        await app.run()


if __name__ == '__main__':
    asyncio.run(main())
