from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from .models import Conversation, ConversationAnalysis
from .serializers import ConversationSerializer, ConversationAnalysisSerializer
from .analysis_engine import analyze_conversation


class ConversationUploadView(generics.CreateAPIView):
    serializer_class = ConversationSerializer

class ReportListView(generics.ListAPIView):
    queryset = ConversationAnalysis.objects.all()
    serializer_class = ConversationAnalysisSerializer

class AnalyseConversationView(APIView):
    def post(self, request):
        conv_id = request.data.get("conversation_id")
        if not conv_id:
            return Response({"error": "conversation_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            conv = Conversation.objects.get(id=conv_id)
        except Conversation.DoesNotExist:
            return Response({"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)

        analysis = analyze_conversation(conv)
        return Response({
            "conversation_id": conv.id,
            "overall_score": analysis.overall_score,
            "sentiment": analysis.sentiment,
            "resolution": analysis.resolution,
        })
