import logging
from django.conf import settings
from django.db import DatabaseError
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, AuthenticationFailed, NotAuthenticated, NotFound, PermissionDenied

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {}

        if isinstance(exc, ValidationError):
            # Laravel style validation response
            errors = {}
            first_error = 'The given data was invalid.'

            if isinstance(exc.detail, dict):
                for field, val in exc.detail.items():
                    if isinstance(val, list):
                        msg_list = []
                        for item in val:
                            if isinstance(item, dict):
                                msg_list.append(item.get('message', str(item)))
                            else:
                                msg_list.append(str(item))
                        errors[field] = msg_list
                    elif isinstance(val, dict):
                        errors[field] = [val.get('message', str(val))]
                    else:
                        errors[field] = [str(val)]

                # Extract first error message
                for field, msg_list in errors.items():
                    if msg_list:
                        first_error = msg_list[0]
                        break
            elif isinstance(exc.detail, list):
                errors['non_field_errors'] = [str(i) for i in exc.detail]
                if errors['non_field_errors']:
                    first_error = errors['non_field_errors'][0]
            else:
                first_error = str(exc.detail)
                errors['error'] = [first_error]

            custom_data = {
                'message': first_error,
                'errors': errors,
            }
            # For auth routes that check success: false
            request = context.get('request')
            if request and request.path.startswith('/api/auth/'):
                custom_data['success'] = False

            response.data = custom_data
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

        elif isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
            msg = str(getattr(exc, 'detail', 'Unauthenticated.'))
            response.data = {
                'message': msg,
            }
            request = context.get('request')
            if request and request.path.startswith('/api/auth/'):
                response.data['success'] = False
            response.status_code = status.HTTP_401_UNAUTHORIZED

        elif isinstance(exc, NotFound):
            response.data = {
                'message': str(getattr(exc, 'detail', 'Not found.')),
            }
            response.status_code = status.HTTP_404_NOT_FOUND

        elif isinstance(exc, PermissionDenied):
            response.data = {
                'message': str(getattr(exc, 'detail', 'This action is unauthorized.')),
            }
            response.status_code = status.HTTP_403_FORBIDDEN

    elif isinstance(exc, DatabaseError):
        logger.error(f"Database error: {exc}", exc_info=True)
        msg = "Database connection or query error. Please verify PostgreSQL connection."
        detail = str(exc) if getattr(settings, 'DEBUG', False) else msg
        response = Response(
            {
                'message': msg,
                'detail': detail,
                'error': 'database_error',
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return response
