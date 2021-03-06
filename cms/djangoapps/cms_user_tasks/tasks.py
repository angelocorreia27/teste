"""
Celery tasks used by cms_user_tasks
"""
import json

from boto.exception import NoAuthHandlerFound
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core import mail
from edx_django_utils.monitoring import set_code_owner_attribute

from common.djangoapps.edxmako.shortcuts import render_to_string
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

LOGGER = get_task_logger(__name__)
TASK_COMPLETE_EMAIL_MAX_RETRIES = 3
TASK_COMPLETE_EMAIL_TIMEOUT = 60


@shared_task(bind=True)
@set_code_owner_attribute
def send_task_complete_email(self, task_name, task_state_text, dest_addr, detail_url, olx_validation_text=None):
    """
    Sending an email to the users when an async task completes.
    """
    retries = self.request.retries

    context = {
        'task_name': task_name,
        'task_status': task_state_text,
        'detail_url': detail_url
    }
    if olx_validation_text:
        try:
            olx_validations = json.loads(olx_validation_text)
            context['olx_validation_errors'] = True
            context['error_summary'] = olx_validations.get('error_summary')
            context['error_report'] = olx_validations.get('error_report')
        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            LOGGER.error(f'Unable to parse CourseOlx validation text: {olx_validation_text}')

    subject = render_to_string('emails/user_task_complete_email_subject.txt', context)
    # Eliminate any newlines
    subject = ''.join(subject.splitlines())
    message = render_to_string('emails/user_task_complete_email.txt', context)

    from_address = configuration_helpers.get_value(
        'email_from_address',
        settings.DEFAULT_FROM_EMAIL
    )

    try:
        mail.send_mail(subject, message, from_address, [dest_addr], fail_silently=False)
        LOGGER.info("Task complete email has been sent to User %s", dest_addr)
    except NoAuthHandlerFound:
        LOGGER.info(
            'Retrying sending email to user %s, attempt # %s of %s',
            dest_addr,
            retries,
            TASK_COMPLETE_EMAIL_MAX_RETRIES
        )
        try:
            self.retry(countdown=TASK_COMPLETE_EMAIL_TIMEOUT, max_retries=TASK_COMPLETE_EMAIL_MAX_RETRIES)
        except MaxRetriesExceededError:
            LOGGER.error(
                'Unable to send task completion email to user from "%s" to "%s"',
                from_address,
                dest_addr,
                exc_info=True
            )
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception(
            'Unable to send task completion email to user from "%s" to "%s"',
            from_address,
            dest_addr,
            exc_info=True
        )
