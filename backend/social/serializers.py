"""Serializers des amitiés et des partages (spec 04 §12 et §13)."""

from rest_framework import serializers

from accounts.models import User, UserStatus
from social.models import (
    FriendRequest,
    ResourceType,
    SharePermission,
    VisibilityType,
)
from social.services import sharing
from social.services.sharing import are_friends


class UserSummarySerializer(serializers.ModelSerializer):
    """Ce qu'un autre compte peut savoir d'un utilisateur.

    Ni email, ni statut, ni horodatages : la recherche sociale ne porte que sur
    le nom d'utilisateur (spec 01 §1), et le reste ne la concerne pas.
    """

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")


class FriendSerializer(UserSummarySerializer):
    """Un ami, et ce qu'il m'a ouvert (spec 04 §12).

    Sérialiseur **distinct** de `UserSummarySerializer` : celui-ci sert aussi à
    `/users/search/` et aux demandes d'ami, où ces drapeaux n'auraient pas de
    sens et renseigneraient sur les partages d'inconnus.

    Ils permettent à l'interface de n'offrir « Son journal » que lorsque le lien
    aboutit. Ce ne sont pas des informations sur les données d'autrui : ce sont
    mes propres accès.
    """

    shares_diary = serializers.SerializerMethodField()
    shares_progress = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = (*UserSummarySerializer.Meta.fields, "shares_diary", "shares_progress")

    def _opened(self, resource_type: str) -> set[int]:
        # Calculé une fois par requête et posé dans le contexte : une requête
        # par ami en ferait autant que la liste est longue.
        return self.context.get("opened", {}).get(resource_type, set())

    def get_shares_diary(self, obj: User) -> bool:
        return obj.id in self._opened(ResourceType.DIARY)

    def get_shares_progress(self, obj: User) -> bool:
        return obj.id in self._opened(ResourceType.PROGRESS)


class FriendRequestSerializer(serializers.ModelSerializer):
    from_user = UserSummarySerializer(read_only=True)
    to_user = UserSummarySerializer(read_only=True)
    direction = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = ("id", "from_user", "to_user", "status", "direction", "created_at")

    def get_direction(self, obj: FriendRequest) -> str:
        """« reçue » ou « envoyée », du point de vue de l'appelant."""
        request = self.context.get("request")
        return "received" if request and obj.to_user_id == request.user.id else "sent"


class FriendRequestCreateSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField()

    def validate_to_user_id(self, value: int) -> int:
        if not User.objects.filter(pk=value, status=UserStatus.ACTIVE).exists():
            raise serializers.ValidationError("Ce compte n'est pas disponible.")
        return value


class SharePermissionSerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    target_user = UserSummarySerializer(read_only=True)
    visibility = serializers.CharField(source="visibility_type", read_only=True)
    resource_name = serializers.SerializerMethodField()

    class Meta:
        model = SharePermission
        fields = (
            "id",
            "owner",
            "target_user",
            "resource_type",
            "resource_id",
            "resource_name",
            "visibility",
            "created_at",
        )

    def get_resource_name(self, obj: SharePermission) -> str:
        """Nom lisible de la ressource, résolu en lot par la vue."""
        names = self.context.get("resource_names", {})
        return names.get((obj.resource_type, obj.resource_id), obj.get_resource_type_display())


class SharePermissionCreateSerializer(serializers.Serializer):
    """Création d'un partage (spec 04 §13).

    Le champ s'appelle `visibility` côté API, comme la spec l'écrit, et
    `visibility_type` en base.
    """

    resource_type = serializers.ChoiceField(choices=ResourceType.choices)
    resource_id = serializers.IntegerField(required=False, allow_null=True)
    visibility = serializers.ChoiceField(choices=VisibilityType.choices)
    target_user_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        user = self.context["request"].user
        resource_type = attrs["resource_type"]
        resource_id = attrs.get("resource_id")

        if sharing.requires_resource_id(resource_type):
            if resource_id is None:
                raise serializers.ValidationError({"resource_id": "Ressource requise."})
            # On ne partage que ce qui nous appartient : la ressource est
            # résolue sur l'appelant, jamais acceptée du client (spec 05 §12).
            if sharing.resolve_owned_resource(user, resource_type, resource_id) is None:
                raise serializers.ValidationError({"resource_id": "Ressource introuvable."})
        elif resource_id is not None:
            raise serializers.ValidationError(
                {"resource_id": "Le journal et la progression n'ont pas d'identifiant."}
            )

        target_id = attrs.get("target_user_id")

        if attrs["visibility"] == VisibilityType.SPECIFIC_USER:
            if target_id is None:
                raise serializers.ValidationError({"target_user_id": "Destinataire requis."})

            target = User.objects.filter(pk=target_id, status=UserStatus.ACTIVE).first()
            if target is None:
                raise serializers.ValidationError({"target_user_id": "Compte introuvable."})

            # La spec 01 §17 lie partage ciblé et amitié : retirer un ami
            # révoque ces partages, donc les accorder hors amitié n'aurait pas
            # de contrepartie.
            if not are_friends(user, target):
                raise serializers.ValidationError(
                    {"target_user_id": "Vous devez être amis pour partager avec ce compte."}
                )
            attrs["target"] = target
        else:
            if target_id is not None:
                raise serializers.ValidationError(
                    {"target_user_id": "Un partage à tous les comptes ne vise personne."}
                )
            attrs["target"] = None

        return attrs
