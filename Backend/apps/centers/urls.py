from django.urls import path
from apps.centers.views import DeliveryCenterListCreateView, DeliveryCenterDetailView

urlpatterns = [
    path('centers', DeliveryCenterListCreateView.as_view(), name='centers-list-create'),
    path('centers/<str:id>', DeliveryCenterDetailView.as_view(), name='centers-detail'),
]
