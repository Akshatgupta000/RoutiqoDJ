from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.serializers import format_delivery_center
from apps.centers.services import (
    list_centers,
    create_center,
    update_center,
    delete_center,
)


class DeliveryCenterListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        centers = list_centers(request.user.id)
        return Response({
            'data': [format_delivery_center(c) for c in centers]
        }, status=status.HTTP_200_OK)

    def post(self, request):
        center = create_center(request.user.id, request.data)
        return Response({
            'data': format_delivery_center(center)
        }, status=status.HTTP_201_CREATED)


class DeliveryCenterDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        center = update_center(request.user.id, str(id), request.data)
        return Response({
            'data': format_delivery_center(center)
        }, status=status.HTTP_200_OK)

    def delete(self, request, id):
        result = delete_center(request.user.id, str(id))
        return Response(result, status=status.HTTP_200_OK)
