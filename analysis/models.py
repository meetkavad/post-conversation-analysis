from django.db import models

class Conversation(models.Model):
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Conversation {self.id}"

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10)  # "user" or "ai"
    text = models.TextField()

    def __str__(self):
        return f"{self.sender}: {self.text[:50]}"

class ConversationAnalysis(models.Model):
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, related_name='analysis')
    clarity_score = models.FloatField(default=0.0)
    relevance_score = models.FloatField(default=0.0)
    sentiment = models.CharField(max_length=20)
    empathy_score = models.FloatField(default=0.0)
    resolution = models.BooleanField(default=False)
    escalation_needed = models.BooleanField(default=False)
    fallback_count = models.IntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)
    overall_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    accuracy_score = models.FloatField(default=0.0)
    completeness_score = models.FloatField(default=0.0)


    def __str__(self):
        return f"Analysis for Conversation {self.conversation.id}"
