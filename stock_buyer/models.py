from typing import Optional

from tortoise import fields
from tortoise.models import Model

from .shioaji import Shioaji


class User(Model):
    id = fields.CharField(max_length=33, pk=True)
    api_key = fields.CharField(max_length=44)
    secret_key = fields.CharField(max_length=44)
    ca_path = fields.TextField()
    ca_passwd = fields.CharField(max_length=255)
    person_id = fields.CharField(max_length=10)
    temp_data: fields.Field[Optional[str]] = fields.TextField(null=True)  # type: ignore

    @property
    def shioaji(self) -> Shioaji:
        return Shioaji(
            api_key=self.api_key,
            secret_key=self.secret_key,
            ca_path=self.ca_path,
            ca_passwd=self.ca_passwd,
            person_id=self.person_id,
        )
