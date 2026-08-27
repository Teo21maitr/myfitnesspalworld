"""Serializers de l'infrastructure partagée."""

from rest_framework import serializers

from common.models import AsyncTask


class AsyncTaskSerializer(serializers.ModelSerializer):
    """État d'une tâche longue (spec 04 §9).

    `result` reste nul tant que la tâche n'a pas abouti, et `error` porte un
    message destiné à l'utilisateur — jamais une trace technique.
    """

    class Meta:
        model = AsyncTask
        fields = ("id", "task_type", "status", "progress", "result", "error", "created_at")
        read_only_fields = fields
