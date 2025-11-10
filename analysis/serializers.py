from rest_framework import serializers
from .models import Conversation, Message, ConversationAnalysis

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'sender', 'text']

class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True)

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'messages']

    def create(self, validated_data):
        messages_data = validated_data.pop('messages')
        conversation = Conversation.objects.create(**validated_data)
        for msg in messages_data:
            Message.objects.create(conversation=conversation, **msg)
        return conversation

class ConversationAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationAnalysis
        fields = '__all__'
