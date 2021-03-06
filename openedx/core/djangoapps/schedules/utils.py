# lint-amnesty, pylint: disable=missing-module-docstring

import datetime
import logging

import pytz
from django.db.models import F, Subquery  # lint-amnesty, pylint: disable=unused-import
from django.db.models.functions import Greatest  # lint-amnesty, pylint: disable=unused-import
from django.db import transaction

from openedx.core.djangoapps.schedules.models import Schedule

LOG = logging.getLogger(__name__)


# TODO: consider using a LoggerAdapter instead of this mixin:
# https://docs.python.org/2/library/logging.html#logging.LoggerAdapter
class PrefixedDebugLoggerMixin:  # lint-amnesty, pylint: disable=missing-class-docstring
    log_prefix = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.log_prefix is None:
            self.log_prefix = self.__class__.__name__

    def log_debug(self, message, *args, **kwargs):
        """
        Wrapper around LOG.debug that prefixes the message.
        """
        LOG.debug(self.log_prefix + ': ' + message, *args, **kwargs)

    def log_info(self, message, *args, **kwargs):
        """
        Wrapper around LOG.info that prefixes the message.
        """
        LOG.info(self.log_prefix + ': ' + message, *args, **kwargs)


def reset_self_paced_schedule(user, course_key, use_availability_date=False):
    """
    Reset the user's schedule if self-paced.

    It does not create a new schedule, just resets an existing one.
    This is used, for example, when a user requests it or when an enrollment mode changes.

    Arguments:
        user (User)
        course_key (CourseKey or str)
        use_availability_date (bool): if False, reset to now, else reset to when user got access to course material
    """
    with transaction.atomic(savepoint=False):
        try:
            schedule = Schedule.objects.select_related('enrollment', 'enrollment__course').get(
                enrollment__user=user,
                enrollment__course__id=course_key,
                enrollment__course__self_paced=True,
            )
        except Schedule.DoesNotExist:
            return

        if use_availability_date:
            enrollment = schedule.enrollment
            schedule.start_date = max(enrollment.created, enrollment.course.start)
            schedule.save()
        else:
            schedule.start_date = datetime.datetime.now(pytz.utc)
            schedule.save()
