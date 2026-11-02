import json
import logging
import threading
import urllib.error
import urllib.request
from django.db import connection, transaction
from apps.core.activity_logging import log_activity
from apps.notifications.models import (
    DeviceToken,
    NotificationAttempt,
    NotificationHistory,
    NotificationRecipientResult,
    NotificationStatus,
)

logger = logging.getLogger('notifications')

EXPO_PUSH_SEND_URL = "https://exp.host/--/api/v2/push/send"
BATCH_SIZE = 100


class PushNotificationService:
    """
    Centralized, reusable push notification dispatch service for CSITABMC CMS.
    Dispatches notifications to enabled Expo Push Tokens for Announcements and Notices,
    tracks delivery history and attempts, and supports safe failure retries.
    """

    @classmethod
    def post_to_expo(cls, messages, url=EXPO_PUSH_SEND_URL):
        """
        Sends a batch of notification messages to the Expo Push API.
        Returns a tuple: (tickets, error_str).
        """
        if not messages:
            return [], None

        payload_bytes = json.dumps(messages).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode('utf-8')
                res_json = json.loads(body)
                tickets = res_json.get('data', [])
                return tickets, None
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            err_msg = f"Expo HTTP {e.code}: {error_body[:200]}"
            logger.error(f"Expo push API HTTP error: {err_msg}")
            return [], err_msg
        except Exception as e:
            err_msg = f"Expo network error: {str(e)[:200]}"
            logger.error(f"Expo push network failure: {err_msg}")
            return [], err_msg

    @classmethod
    def dispatch_notification(
        cls,
        title,
        body,
        source_module,
        source_id="",
        source_title="",
        data=None,
        target_tokens=None,
        existing_history=None,
        is_retry=False,
    ):
        """
        Core synchronous dispatch method:
        1. Prepares/retrieves NotificationHistory.
        2. Retrieves target devices (active tokens, or subset for retry).
        3. Batches sends to Expo API.
        4. Logs NotificationAttempt and updates recipient results.
        5. Updates NotificationHistory status and counts.
        6. Logs automated activity log if not a manual retry.
        """
        data = data or {}

        # 1. Obtain or create NotificationHistory
        if existing_history:
            history = existing_history
        else:
            history = NotificationHistory.objects.create(
                source_module=source_module,
                source_id=str(source_id),
                source_title=source_title or title,
                title=title,
                body=body,
                data=data,
                status=NotificationStatus.PENDING,
            )

        # 2. Determine target tokens
        if target_tokens is not None:
            devices = list(target_tokens)
        elif is_retry:
            # Query only previously failed devices
            failed_token_ids = NotificationRecipientResult.objects.filter(
                notification=history,
                status=NotificationRecipientResult.ResultStatus.FAILED
            ).values_list('device_token_id', flat=True)
            devices = list(DeviceToken.objects.filter(id__in=failed_token_ids, enabled=True))
        else:
            devices = list(DeviceToken.objects.active())

        total_targeted = len(devices)
        if total_targeted == 0:
            history.status = NotificationStatus.SENT if not is_retry else history.status
            history.total_devices = total_targeted
            history.save(update_fields=['status', 'total_devices', 'updated_at'])

            NotificationAttempt.objects.create(
                notification=history,
                attempt_number=history.attempts.count() + 1,
                targeted_count=0,
                accepted_count=0,
                failed_count=0,
                status=NotificationStatus.SENT,
                error_summary="No active devices to target.",
            )
            return history

        # 3. Batch and dispatch
        accepted_count = 0
        failed_count = 0
        error_messages = []
        attempt_number = history.attempts.count() + 1

        for i in range(0, total_targeted, BATCH_SIZE):
            chunk = devices[i : i + BATCH_SIZE]
            messages = [
                {
                    "to": dev.token,
                    "title": history.title,
                    "body": history.body,
                    "sound": "default",
                    "channelId": "notices",
                    "data": history.data,
                }
                for dev in chunk
            ]

            tickets, batch_error = cls.post_to_expo(messages)

            if batch_error:
                error_messages.append(batch_error)
                failed_count += len(chunk)
                for dev in chunk:
                    NotificationRecipientResult.objects.update_or_create(
                        notification=history,
                        device_token=dev,
                        defaults={
                            'status': NotificationRecipientResult.ResultStatus.FAILED,
                            'error_message': batch_error[:255],
                        }
                    )
            else:
                for idx, ticket in enumerate(tickets):
                    dev = chunk[idx] if idx < len(chunk) else None
                    if not dev:
                        continue

                    ticket_status = ticket.get('status')
                    if ticket_status == 'ok':
                        accepted_count += 1
                        NotificationRecipientResult.objects.update_or_create(
                            notification=history,
                            device_token=dev,
                            defaults={
                                'status': NotificationRecipientResult.ResultStatus.ACCEPTED,
                                'error_message': '',
                            }
                        )
                    else:
                        failed_count += 1
                        ticket_err = ticket.get('message') or ticket.get('details', {}).get('error', 'Send error')
                        error_messages.append(f"Device {dev.id}: {ticket_err}")

                        # Auto-disable unregistered tokens
                        is_unregistered = ticket.get('details', {}).get('error') == 'DeviceNotRegistered'
                        if is_unregistered:
                            dev.enabled = False
                            dev.save(update_fields=['enabled', 'updated_at'])
                            result_status = NotificationRecipientResult.ResultStatus.INVALID
                        else:
                            result_status = NotificationRecipientResult.ResultStatus.FAILED

                        NotificationRecipientResult.objects.update_or_create(
                            notification=history,
                            device_token=dev,
                            defaults={
                                'status': result_status,
                                'error_message': str(ticket_err)[:255],
                            }
                        )

        # 4. Determine attempt status
        if accepted_count == total_targeted:
            attempt_status = NotificationStatus.SENT
        elif accepted_count > 0:
            attempt_status = NotificationStatus.PARTIALLY_SENT
        else:
            attempt_status = NotificationStatus.FAILED

        # 5. Record Attempt
        NotificationAttempt.objects.create(
            notification=history,
            attempt_number=attempt_number,
            targeted_count=total_targeted,
            accepted_count=accepted_count,
            failed_count=failed_count,
            status=attempt_status,
            error_summary="; ".join(error_messages[:5])[:500],
        )

        # 6. Update History
        if is_retry:
            history.retry_count += 1
            # Recompute total accepted across attempts
            total_accepted = NotificationRecipientResult.objects.filter(
                notification=history,
                status=NotificationRecipientResult.ResultStatus.ACCEPTED
            ).count()
            total_failed = NotificationRecipientResult.objects.filter(
                notification=history,
                status=NotificationRecipientResult.ResultStatus.FAILED
            ).count()

            history.accepted_count = total_accepted
            history.failed_count = total_failed
            if total_failed == 0 and total_accepted > 0:
                history.status = NotificationStatus.SENT
            elif total_accepted > 0:
                history.status = NotificationStatus.PARTIALLY_SENT
            else:
                history.status = NotificationStatus.FAILED
        else:
            history.total_devices = total_targeted
            history.accepted_count = accepted_count
            history.failed_count = failed_count
            history.status = attempt_status

        if error_messages:
            history.error_summary = "; ".join(error_messages[:5])[:500]

        history.save(update_fields=['status', 'total_devices', 'accepted_count', 'failed_count', 'retry_count', 'error_summary', 'updated_at'])

        # 7. Record automated activity log (if initial automated send)
        if not is_retry:
            log_activity(
                user=None,
                action="dispatch",
                module="notifications",
                target_id=str(history.id),
                target_repr=f"Notification #{history.id}: {history.title[:50]}",
                description=f"System dispatched push notification for {history.source_module} '{history.source_title}' ({accepted_count} accepted, {failed_count} failed)",
                details={
                    "source_module": history.source_module,
                    "source_id": history.source_id,
                    "total_devices": total_targeted,
                    "accepted_count": accepted_count,
                    "failed_count": failed_count,
                    "status": history.status,
                }
            )

        return history

    @classmethod
    def send_async(cls, title, body, source_module, source_id="", source_title="", data=None):
        """
        Launches push notification dispatch asynchronously in a background thread
        so HTTP responses return immediately without waiting on Expo network calls.
        """
        def _worker():
            try:
                cls.dispatch_notification(
                    title=title,
                    body=body,
                    source_module=source_module,
                    source_id=source_id,
                    source_title=source_title,
                    data=data,
                )
            except Exception as e:
                logger.exception(f"Background push notification dispatch failed: {e}")
            finally:
                connection.close()

        def _start_thread():
            thread = threading.Thread(target=_worker, daemon=True)
            thread.start()

        # If inside a transaction, schedule after commit; otherwise start immediately
        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(_start_thread)
        else:
            _start_thread()
