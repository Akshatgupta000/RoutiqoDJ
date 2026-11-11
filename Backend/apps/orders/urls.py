from django.urls import path
from apps.orders.views import (
    OrderListCreateView,
    OrderDetailView,
    OrderAssignView,
    OrderDateCountsView,
    OrderBulkCountsView,
    OrderClearByDateView,
    OrderDeleteCompletedView,
    OrderDeletePendingView,
    OrderMarkAllDeliveredView,
)

urlpatterns = [
    path('orders', OrderListCreateView.as_view(), name='orders-list-create'),
    path('orders/date-counts', OrderDateCountsView.as_view(), name='orders-date-counts'),
    path('orders/bulk-counts', OrderBulkCountsView.as_view(), name='orders-bulk-counts'),
    path('orders/clear-by-date', OrderClearByDateView.as_view(), name='orders-clear-by-date'),
    path('orders/completed', OrderDeleteCompletedView.as_view(), name='orders-delete-completed'),
    path('orders/pending', OrderDeletePendingView.as_view(), name='orders-delete-pending'),
    path('orders/mark-all-delivered', OrderMarkAllDeliveredView.as_view(), name='orders-mark-all-delivered'),
    path('orders/<str:id>/assign', OrderAssignView.as_view(), name='orders-assign'),
    path('orders/<str:id>', OrderDetailView.as_view(), name='orders-detail'),
]
