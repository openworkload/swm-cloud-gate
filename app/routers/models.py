import typing

from pydantic import BaseModel


class PartInfo(BaseModel):
    id: str
    name: str
    master_public_ip: str = ""
    master_private_ip: str = ""
    compute_instances_ips: typing.List[str] = []
    status: typing.Optional[str] = None
    created: typing.Optional[str] = None
    updated: typing.Optional[str] = None
    description: typing.Optional[str] = None


class ImageInfo(BaseModel):
    id: str
    name: str
    extra: dict[str, typing.Any] = {}


class Flavor(BaseModel):
    id: str
    name: str
    cpus: int
    mem: int
    storage: int
    price: float


class HttpBody(BaseModel):
    pem_data: bytes
