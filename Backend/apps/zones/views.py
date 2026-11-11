from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from apps.zones.services import (
    list_zones,
    save_zones,
    check_coordinates,
)


class ServiceZoneListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        zones = list_zones(request.user.id)
        return Response(zones, status=status.HTTP_200_OK)


class ServiceZoneGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        zones_data = request.data.get('zones')
        if zones_data is None:
            raise ValidationError({'zones': ['The zones field is required.']})

        save_zones(request.user.id, zones_data)
        return Response({
            'message': 'Service zones updated successfully'
        }, status=status.HTTP_200_OK)


class ServiceZoneCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('lat') or request.data.get('lat')
        lng = request.query_params.get('lng') or request.data.get('lng')

        if lat is None or lng is None:
            raise ValidationError({
                'lat': ['The latitude field is required.'],
                'lng': ['The longitude field is required.'],
            })

        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (ValueError, TypeError):
            raise ValidationError({'message': 'Latitude and longitude must be numbers.'})

        result = check_coordinates(request.user.id, lat_f, lng_f)
        if not result:
            return Response({'message': 'No hub found for these coordinates'}, status=status.HTTP_404_NOT_FOUND)

        return Response(result, status=status.HTTP_200_OK)

