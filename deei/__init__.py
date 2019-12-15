from __future__ import annotations

from dataclasses import dataclass
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Optional, Iterable, Iterator, Tuple, Collection, List, get_type_hints

from .helpers import *


@asynccontextmanager
async def bootstrap(target):
    async with DeeiContext(target) as context:
        yield await context.get_target()


def injectable():

    def decorator(target):
        setattr(target, '_deei_injectable_', True)
        return target

    return decorator


def is_injectable(target):
    return getattr(target, '_deei_injectable_', False)


def module(providers: Optional[Iterable] = None,
           exports: Optional[Iterable] = None,
           imports: Optional[Iterable] = None):

    providers = providers or []
    exports = exports or []
    imports = imports or []

    def decorator(target):
        setattr(target, '_deei_module_', ModuleMetadata(providers, exports, imports))
        return target

    return decorator


def is_module(target) -> bool:
    return hasattr(target, '_deei_module_')


def get_module_metadata(target) -> ModuleMetadata:
    return getattr(target, '_deei_module_')


def get_dependency_hints(target) -> Iterator[Tuple[str, Any]]:
    return get_type_hints(target.__init__).items()


def get_dependency_name(target) -> str:
    return camelcase_into_snakecase(target.__name__)


@dataclass
class ModuleMetadata:
    providers: Collection
    exports: Collection
    imports: Collection


class IDeeiContext:

    async def get_target(self): ...

    async def get_dependency(self, name: str): ...

    def get_name(self) -> str: ...

    def can_provide(self, name: str) -> bool:
        """True if Context can provide a dependency."""

    def can_export(self, name: str) -> bool:
        """True if Context can provide a dependency to its parent Context."""


class DeeiNullContext(IDeeiContext):

    async def get_target(self):
        raise NotImplementedError(f'{type(self).__name__} has no target')

    async def get_dependency(self, name: str):
        raise InjectionError(f'{type(self).__name__} cannot find dependency {name}')

    def get_name(self) -> str:
        return ''

    def can_provide(self, name: str) -> bool:
        return False

    def can_export(self, name: str) -> bool:
        return False


class DeeiContext(IDeeiContext):

    def __init__(self, target, parent: DeeiContext = DeeiNullContext()) -> None:
        self._target = target
        self._parent = parent

        self._aentered = False
        self._exit_stack = AsyncExitStack()

        self._providers: List[DeeiContext] = []
        self._imports: List[DeeiContext] = []
        self._exports: List[DeeiContext] = []

        self._dependencies = {}

        self._is_module = is_module(self._target)
        if is_module(self._target):
            module_metadata = get_module_metadata(self._target)

            for provider in module_metadata.providers:
                provider_context = DeeiContext(provider, self)
                self._providers.append(provider_context)

            for import_ in module_metadata.imports:
                import_context = DeeiContext(import_, self)
                self._imports.append(import_context)
                if import_ in module_metadata.exports:
                    self._exports.append(import_context)

        self._target_instance = None
        self._target_is_initialized = False

    def get_name(self) -> str:
        return camelcase_into_snakecase(self._target.__name__)

    def can_provide(self, name: str) -> bool:
        for provider in self._providers:
            if name == provider.get_name():
                return True

        for import_ in self._imports:
            if import_.can_provide(name):
                return True

        if self._parent.can_provide(name):
            return True

        return False

    def can_export(self, name: str) -> bool:
        if not self._is_module:
            return False

        for provider in self._providers:
            if name == provider.get_name():
                return True

        for export in self._exports:
            if export.can_provide(name):
                return True

        return False

    async def get_target(self):
        return self._target_instance

    async def get_dependency(self, name: str):
        if name in self._dependencies:
            return self._dependencies[name]

        for provider in self._providers:
            if name == provider.get_name():
                await self._exit_stack.enter_async_context(provider)
                dependency = self._dependencies[name] = await provider.get_target()
                return dependency

        for import_ in self._imports:
            if import_.can_export(name):
                await self._exit_stack.enter_async_context(import_)
                dependency = self._dependencies[name] = await import_.get_dependency(name)
                return dependency

        if self._parent.can_provide(name):
            return await self._parent.get_dependency(name)

        raise InjectionError(f'{self!r}: Failed to provide dependency ', name)

    async def __aenter__(self) -> DeeiContext:
        if self._aentered:
            return self

        to_inject = {}
        for attr_name, attr_hint in get_type_hints(self._target.__init__).items():
            if attr_name == 'return':
                continue
            to_inject[attr_name] = await self.get_dependency(attr_name)

        instance = self._target(**to_inject)

        if hasattr(instance, '__aenter__') and hasattr(instance, '__aexit__'):
            print(f'{type(instance).__name__} is async context manager!')
            await self._exit_stack.enter_async_context(instance)

        self._target_instance = instance
        self._target_is_initialized = True

        self._aentered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        print(f'{self!r}: __aexit__')
        await self._exit_stack.aclose()
        return None

    def __repr__(self) -> str:
        return f'{type(self).__name__}(target={self._target!r})'


class InjectionError(TypeError):
    pass
