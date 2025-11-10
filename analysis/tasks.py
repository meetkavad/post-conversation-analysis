from datetime import timedelta
from django.utils import timezone
from background_task import background
from .models import Conversation, ConversationAnalysis
from .analysis_engine import analyze_conversation

@background(schedule=86400)  # runs every 24 hours
def update_analytics_task():

    now = timezone.now()
    since = now - timedelta(days=1)

    # Fetch only conversations created in the last 24h and not yet analyzed
    new_conversations = Conversation.objects.filter(
        created_at__gte=since
    ).exclude(analysis__isnull=False)

    print(f"Found {new_conversations.count()} new conversations to analyze.")

    for conv in new_conversations:
        try:
            analyze_conversation(conv)
            print(f"Analyzed conversation: {conv.id}")
        except Exception as e:
            print(f"Failed to analyze conversation {conv.id}: {e}")

    print("Analytics update complete.")
