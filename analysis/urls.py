from django.urls import path
from .views import ConversationUploadView, ReportListView, AnalyseConversationView

urlpatterns = [
    path('conversations/', ConversationUploadView.as_view(), name='conversation-upload'),
    path('reports/', ReportListView.as_view(), name='report-list'),
    path('analyse/', AnalyseConversationView.as_view(), name='analyse-conversation'),
]
