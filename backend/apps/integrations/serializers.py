from rest_framework import serializers
from apps.notifications.models import NotificationChannel, NotificationStatus


class NotificationClaimSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField(required=False, allow_null=True)
    registration_id = serializers.UUIDField(required=False, allow_null=True)
    event_id = serializers.UUIDField(required=False, allow_null=True)
    channel = serializers.ChoiceField(
        choices=NotificationChannel.choices,
        default=NotificationChannel.WHATSAPP,
    )

    def validate(self, attrs):
        if not attrs.get("notification_id") and not attrs.get("registration_id") and not attrs.get("event_id"):
            raise serializers.ValidationError(
                "At least one of 'notification_id', 'registration_id', or 'event_id' is required."
            )
        return attrs


class AutomationCallbackSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField(required=True)
    channel = serializers.ChoiceField(
        choices=NotificationChannel.choices,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=[NotificationStatus.SENT, NotificationStatus.FAILED],
        required=True,
    )
    external_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    error = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
