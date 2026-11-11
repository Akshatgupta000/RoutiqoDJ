from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.serializers import format_vehicle
from apps.vehicles.services import (
    list_vehicles,
    create_vehicle,
    update_vehicle,
    reset_fleet,
    delete_vehicle,
)


class VehicleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        center_id = request.query_params.get('delivery_center_id')
        vehicles = list_vehicles(request.user.id, center_id)
        return Response({
            'data': [format_vehicle(v, load_center=True) for v in vehicles]
        }, status=status.HTTP_200_OK)

    def post(self, request):
        vehicle = create_vehicle(request.user.id, request.data)
        return Response({
            'data': format_vehicle(vehicle, load_center=True)
        }, status=status.HTTP_201_CREATED)


class VehicleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        vehicle = update_vehicle(request.user.id, str(id), request.data)
        return Response({
            'data': format_vehicle(vehicle, load_center=True)
        }, status=status.HTTP_200_OK)

    def delete(self, request, id):
        delete_vehicle(request.user.id, str(id))
        return Response(None, status=status.HTTP_204_NO_CONTENT)


class VehicleResetFleetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        center_id = request.data.get('delivery_center_id') or request.query_params.get('delivery_center_id')
        res = reset_fleet(request.user.id, center_id)
        return Response(res, status=status.HTTP_200_OK)
