import json
import urllib.parse
from datetime import date, timedelta
import peewee as pw
from src.settings import settings
from src.entities.analytics import UsageEvent, DailyStat, database_proxy
import structlog

log = structlog.get_logger()


def init_db():
    parsed = urllib.parse.urlparse(settings.database_url)
    db = pw.PostgresqlDatabase(
        parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
    )
    database_proxy.initialize(db)
    db.connect(reuse_if_open=True)
    db.create_tables([UsageEvent, DailyStat], safe=True)
    log.info("analytics_db_initialized")


class AnalyticsService:
    def record_event(self, event_type: str, user_id: str | None, metadata: dict) -> None:
        UsageEvent.create(
            user_id=user_id,
            event_type=event_type,
            metadata=json.dumps(metadata),
        )

    def upsert_daily_stat(self, user_id: str, label: str, ai_score: float, char_count: int) -> None:
        today = date.today()
        stat, created = DailyStat.get_or_create(
            user_id=user_id,
            date=today,
            defaults={"scan_count": 0, "ai_count": 0, "human_count": 0, "avg_ai_score": 0.0, "total_chars": 0},
        )
        stat.scan_count += 1
        if label == "ai":
            stat.ai_count += 1
        else:
            stat.human_count += 1
        # Running avg
        prev_total = stat.avg_ai_score * (stat.scan_count - 1)
        stat.avg_ai_score = (prev_total + ai_score) / stat.scan_count
        stat.total_chars += char_count
        stat.save()

    def get_dashboard_stats(self, user_id: str) -> dict:
        today = date.today()
        last_30 = today - timedelta(days=30)

        stats = list(
            DailyStat.select()
            .where(DailyStat.user_id == user_id, DailyStat.date >= last_30)
            .order_by(DailyStat.date.asc())
        )

        total_scans = sum(s.scan_count for s in stats)
        total_ai = sum(s.ai_count for s in stats)
        total_human = sum(s.human_count for s in stats)
        avg_score = sum(s.avg_ai_score * s.scan_count for s in stats) / total_scans if total_scans > 0 else 0.0

        trend = [
            {
                "date": str(s.date),
                "scan_count": s.scan_count,
                "ai_count": s.ai_count,
                "human_count": s.human_count,
                "avg_ai_score": round(s.avg_ai_score, 4),
            }
            for s in stats
        ]

        return {
            "total_scans": total_scans,
            "total_ai": total_ai,
            "total_human": total_human,
            "ai_ratio": round(total_ai / total_scans, 4) if total_scans > 0 else 0.0,
            "avg_ai_score": round(avg_score, 4),
            "trend": trend,
        }

    def get_system_overview(self) -> dict:
        today = date.today()
        last_30 = today - timedelta(days=30)

        all_stats = list(DailyStat.select().where(DailyStat.date >= last_30))

        total_scans = sum(s.scan_count for s in all_stats)
        total_ai = sum(s.ai_count for s in all_stats)
        total_human = sum(s.human_count for s in all_stats)
        active_users = len(set(str(s.user_id) for s in all_stats))
        total_chars = sum(s.total_chars for s in all_stats)

        # Aggregate trend by date across all users
        by_date: dict = {}
        for s in all_stats:
            d = str(s.date)
            if d not in by_date:
                by_date[d] = {"date": d, "scan_count": 0, "ai_count": 0, "human_count": 0}
            by_date[d]["scan_count"] += s.scan_count
            by_date[d]["ai_count"] += s.ai_count
            by_date[d]["human_count"] += s.human_count

        trend = sorted(by_date.values(), key=lambda x: x["date"])

        return {
            "total_scans_30d": total_scans,
            "total_ai_30d": total_ai,
            "total_human_30d": total_human,
            "ai_ratio_30d": round(total_ai / total_scans, 4) if total_scans > 0 else 0.0,
            "active_users_30d": active_users,
            "total_chars_30d": total_chars,
            "trend": trend,
        }
