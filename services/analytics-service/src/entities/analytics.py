import uuid
from datetime import datetime, date
import peewee as pw

database_proxy = pw.DatabaseProxy()


class BaseModel(pw.Model):
    id = pw.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = pw.DateTimeField(default=datetime.utcnow)

    class Meta:
        database = database_proxy


class UsageEvent(BaseModel):
    user_id = pw.UUIDField(index=True, null=True)
    event_type = pw.CharField(max_length=50, index=True)
    metadata = pw.TextField(default="{}")  # JSON

    class Meta:
        table_name = "usage_events"


class DailyStat(BaseModel):
    user_id = pw.UUIDField(index=True)
    date = pw.DateField(index=True)
    scan_count = pw.IntegerField(default=0)
    ai_count = pw.IntegerField(default=0)
    human_count = pw.IntegerField(default=0)
    avg_ai_score = pw.FloatField(default=0.0)
    total_chars = pw.IntegerField(default=0)

    class Meta:
        table_name = "daily_stats"
        indexes = ((("user_id", "date"), True),)  # unique constraint
