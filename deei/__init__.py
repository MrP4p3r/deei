from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Optional, get_type_hints


@asynccontextmanager
async def bootstrap(cls):
    async with DeeiContext(cls) as context:
        yield await context.get_target()


class DeeiContext:

    def __init__(self, target, parent: Optional[DeeiContext] = None) -> None:
        self._target = target
        self._parent = parent

        self._exit_stack = AsyncExitStack()
        self._subcontexts = {}
        for attr_name, attr_hint in get_type_hints(target).items():
            if not (self._parent and self._parent.can_provide(attr_name)):
                self._subcontexts[attr_name] = DeeiContext(attr_hint, self)

        self._initialized_dependencies = {}
        self._target_instance = None
        self._target_is_initialized = False

    async def get_target(self):
        return self._target_instance

    def can_provide(self, name: str) -> bool:
        return (
            name in self._subcontexts
            or self._parent and self._parent.can_provide(name)
        )

    async def _get_dependency(self, name: str):
        if name in self._initialized_dependencies:
            return self._initialized_dependencies[name]
        elif name in self._subcontexts:
            subcontext: DeeiContext = self._subcontexts[name]
            await self._exit_stack.enter_async_context(subcontext)
            result = self._initialized_dependencies[name] = await subcontext.get_target()
            return result
        elif self._parent and self._parent.can_provide(name):
            return await self._parent._get_dependency(name)
        else:
            raise InjectionError(f'{self!r}: Failed to provide dependency', name)

    async def __aenter__(self) -> DeeiContext:
        to_inject = {}
        for attr_name, attr_hint in get_type_hints(self._target).items():
            to_inject[attr_name] = await self._get_dependency(attr_name)

        instance = self._target.__new__(self._target)
        instance.__dict__.update(to_inject)
        instance.__init__()

        if hasattr(instance, '__aenter__') and hasattr(instance, '__aexit__'):
            print(f'{type(instance).__name__} is async context manager!')
            await self._exit_stack.enter_async_context(instance)

        self._target_instance = instance
        self._target_is_initialized = True

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        print(f'{self!r}: __aexit__')
        await self._exit_stack.aclose()
        return None

    def __repr__(self) -> str:
        return f'{type(self).__name__}(target={self._target!r})'


class InjectionError(TypeError):
    pass
