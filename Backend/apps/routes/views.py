import datetime
from typing import Any, Optional
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, ValidationError

from apps.routes.services import (
    list_routes,
    get_route_by_id,
    generate_routes,
    regenerate_routes_for_center,
    generate_route_for_vehicle,
    clear_routes,
)


def parse_departure_at(val: Any) -> Optional[datetime.datetime]:
    if not val:
        return None
    if isinstance(val, datetime.datetime):
        return val
    try:
        # Support ISO formats like 2026-05-05T08:00:00Z
        return datetime.datetime.fromisoformat(str(val).replace('Z', '+00:00'))
    except Exception:
        return None


class RouteListGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        routes = list_routes(request.user.id)
        return Response({'routes': routes}, status=status.HTTP_200_OK)

    def post(self, request):
        center_id = request.data.get('delivery_center_id')
        date = request.data.get('date')
        dep_val = request.data.get('departure_at')
        departure_at = parse_departure_at(dep_val)

        comparisons = generate_routes(
            user_id=request.user.id,
            delivery_center_id=center_id,
            departure_at=departure_at,
            date=date,
        )
        return Response({'comparisons': comparisons}, status=status.HTTP_201_CREATED)


class RouteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        route = get_route_by_id(request.user.id, str(id))
        if not route:
            raise NotFound('Route not found.')
        return Response(route, status=status.HTTP_200_OK)


class RouteRegenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, center_id):
        date = request.data.get('date') or request.query_params.get('date')
        dep_val = request.data.get('departure_at')
        departure_at = parse_departure_at(dep_val)

        comparisons = regenerate_routes_for_center(
            user_id=request.user.id,
            delivery_center_id=str(center_id),
            departure_at=departure_at,
            date=date,
        )
        return Response({'comparisons': comparisons}, status=status.HTTP_200_OK)


class RouteClearView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        center_id = request.data.get('delivery_center_id') or request.query_params.get('delivery_center_id')
        clear_routes(request.user.id, center_id)
        return Response({'message': 'Routes cleared and orders reverted to pending.'}, status=status.HTTP_200_OK)


class RouteForVehicleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_id):
        dep_val = request.data.get('departure_at')
        departure_at = parse_departure_at(dep_val)
        res = generate_route_for_vehicle(request.user.id, str(vehicle_id), departure_at)
        return Response(res, status=status.HTTP_201_CREATED)
