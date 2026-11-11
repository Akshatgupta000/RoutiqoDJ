import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.serializers import format_order
from apps.orders.services import (
    list_orders_paginated,
    create_order,
    update_order,
    assign_order,
    delete_order,
    get_date_counts,
    get_bulk_counts,
    clear_orders_by_date,
    delete_completed_orders,
    delete_pending_orders,
    delete_all_orders,
    mark_all_delivered,
)


class OrderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            per_page = int(request.query_params.get('per_page', 15))
        except (ValueError, TypeError):
            per_page = 15
        per_page = min(max(per_page, 1), 100)

        try:
            page = int(request.query_params.get('page', 1))
        except (ValueError, TypeError):
            page = 1
        page = max(page, 1)

        status_filter = request.query_params.get('status')
        date_filter = request.query_params.get('date')
        center_id = request.query_params.get('delivery_center_id')

        base_url = request.build_absolute_uri(request.path)
        result = list_orders_paginated(
            user_id=request.user.id,
            page=page,
            per_page=per_page,
            status_filter=status_filter,
            date_filter=date_filter,
            delivery_center_id=center_id,
            base_url=base_url,
        )
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request):
        order = create_order(request.user.id, request.data)
        return Response({
            'data': format_order(order)
        }, status=status.HTTP_201_CREATED)

    def delete(self, request):
        date = request.query_params.get('date') or request.data.get('date')
        count = delete_all_orders(request.user.id, date)
        return Response({
            'success': True,
            'deleted_count': count
        }, status=status.HTTP_200_OK)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        order = update_order(request.user.id, str(id), request.data)
        return Response({
            'data': format_order(order)
        }, status=status.HTTP_200_OK)

    def delete(self, request, id):
        delete_order(request.user.id, str(id))
        return Response(None, status=status.HTTP_204_NO_CONTENT)


class OrderAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        order = assign_order(request.user.id, str(id))
        return Response({
            'data': format_order(order)
        }, status=status.HTTP_200_OK)


class OrderDateCountsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = datetime.datetime.now()
        year = int(request.query_params.get('year', now.year))
        month = int(request.query_params.get('month', now.month))
        counts = get_date_counts(request.user.id, year, month)
        return Response(counts, status=status.HTTP_200_OK)


class OrderBulkCountsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date = request.query_params.get('date')
        counts = get_bulk_counts(request.user.id, date)
        return Response(counts, status=status.HTTP_200_OK)


class OrderClearByDateView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        date = request.query_params.get('date')
        count = clear_orders_by_date(request.user.id, date)
        return Response({'deleted': count}, status=status.HTTP_200_OK)


class OrderDeleteCompletedView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        date = request.query_params.get('date')
        count = delete_completed_orders(request.user.id, date)
        return Response({
            'success': True,
            'deleted_count': count
        }, status=status.HTTP_200_OK)


class OrderDeletePendingView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        date = request.query_params.get('date')
        count = delete_pending_orders(request.user.id, date)
        return Response({
            'success': True,
            'deleted_count': count
        }, status=status.HTTP_200_OK)


class OrderMarkAllDeliveredView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        date = request.query_params.get('date') or request.data.get('date')
        count = mark_all_delivered(request.user.id, date)
        return Response({
            'success': True,
            'updated_count': count
        }, status=status.HTTP_200_OK)
