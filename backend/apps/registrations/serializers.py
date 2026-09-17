import re
import phonenumbers
from phonenumbers import NumberParseException
from rest_framework import serializers
from apps.workshops.models import Workshop
from .models import Registration


class RegistrationCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        required=True,
        error_messages={
            "required": "Full name is required.",
            "blank": "Full name cannot be blank.",
        },
    )
    email = serializers.EmailField(
        required=True,
        error_messages={
            "required": "Email address is required.",
            "blank": "Email address cannot be blank.",
            "invalid": "Enter a valid email address.",
        },
    )
    phone_number = serializers.CharField(
        max_length=30,
        required=True,
        trim_whitespace=True,
        error_messages={
            "required": "Phone number is required.",
            "blank": "Phone number cannot be blank.",
        },
    )

    def validate_full_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Full name must be at least 2 characters long.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Full name cannot exceed 150 characters.")
        return cleaned

    def validate_email(self, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise serializers.ValidationError("Email cannot be blank.")
        return cleaned

    def validate_phone_number(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Phone number cannot be blank.")
        try:
            # Default to India (IN) region if country code is not prefixed with '+'
            parsed = phonenumbers.parse(
                cleaned,
                "IN" if not cleaned.startswith("+") else None
            )
        except NumberParseException as exc:
            raise serializers.ValidationError(
                "Invalid phone number format. Please provide a valid phone number with country code (e.g. +919876543210)."
            ) from exc

        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError(
                "Invalid phone number. Please check the digits and country code."
            )

        # Standardize to strict E.164 format
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class RegistrationResponseSerializer(serializers.Serializer):
    registration_id = serializers.UUIDField(source="id")
    full_name = serializers.CharField()
    email = serializers.CharField(source="normalized_email")
    phone_number = serializers.CharField()
    workshop = serializers.SerializerMethodField()
    message = serializers.CharField()

    def get_workshop(self, obj) -> dict:
        return {
            "title": obj.workshop.title,
            "scheduled_at": obj.workshop.scheduled_at.isoformat(),
            "timezone": obj.workshop.timezone,
        }
