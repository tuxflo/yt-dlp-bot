from typing import ClassVar
from urllib.parse import urlsplit

from ytdl_opts.per_host._base import AbstractHostConfig


class HostConfRegistry(type):
    REGISTRY: ClassVar[dict[str, type[AbstractHostConfig]]] = {}
    HOST_TO_CLS_MAP: ClassVar[dict[str | None, type[AbstractHostConfig]]] = {}

    def __new__(
        cls: type['HostConfRegistry'],
        name: str,
        bases: tuple[type[AbstractHostConfig]],
        attrs: dict,
    ) -> type[AbstractHostConfig]:
        host_cls: type[AbstractHostConfig] = type.__new__(cls, name, bases, attrs)
        cls.REGISTRY[host_cls.__name__] = host_cls

        cls._build_host_to_cls_map(host_cls=host_cls, hostnames=attrs['HOSTNAMES'])
        return host_cls

    @classmethod
    def get_registry(cls) -> dict[str, type[AbstractHostConfig]]:
        return cls.REGISTRY.copy()

    @classmethod
    def get_host_to_cls_map(cls) -> dict[str | None, type[AbstractHostConfig]]:
        return cls.HOST_TO_CLS_MAP.copy()

    @classmethod
    def _build_host_to_cls_map(
        cls, host_cls: type[AbstractHostConfig], hostnames: tuple[str, ...] | None
    ) -> None:
        if hostnames is None:
            cls.HOST_TO_CLS_MAP[None] = host_cls
            return

        for host in hostnames:
            cls.HOST_TO_CLS_MAP[host] = host_cls


def get_host_conf(url: str) -> AbstractHostConfig:
    """Return host config instance matching the URL's hostname."""
    host_to_cls_map = HostConfRegistry.get_host_to_cls_map()
    host_cls = host_to_cls_map.get(urlsplit(url).netloc, host_to_cls_map[None])
    return host_cls(url=url)
