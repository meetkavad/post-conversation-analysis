from django.apps import AppConfig
from datetime import datetime, timedelta

class AnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analysis'

    def ready(self):
        from analysis.tasks import update_analytics_task
        # schedule the first run for the next midnight
        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        delay = (next_midnight - now).total_seconds()
        update_analytics_task(schedule=delay, repeat=86400)
