import uuid
from datetime import datetime
import peewee as pw


database_proxy = pw.DatabaseProxy()


class BaseModel(pw.Model):
    id = pw.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = pw.DateTimeField(default=datetime.utcnow)
    updated_at = pw.DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        database = database_proxy
