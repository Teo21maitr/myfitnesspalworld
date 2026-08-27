"""Réglages globaux (spec 03 §13, spec 07 §11)."""

import pytest

from common.models import AppSetting

pytestmark = pytest.mark.django_db


class TestGetBool:
    def test_un_reglage_absent_renvoie_la_valeur_par_defaut(self):
        assert AppSetting.get_bool("inexistant", default=True) is True
        assert AppSetting.get_bool("inexistant", default=False) is False

    @pytest.mark.parametrize("stored", [True, False])
    def test_un_booleen_est_lu_tel_quel(self, stored):
        AppSetting.objects.create(key="ai_enabled", value=stored)

        assert AppSetting.get_bool("ai_enabled", default=not stored) is stored

    @pytest.mark.parametrize(
        "stored",
        [
            pytest.param("true", id="chaine-vraie"),
            # « false » est une chaîne non vide, donc vraie : l'interpréter
            # comme un booléen inverserait le réglage.
            pytest.param("false", id="chaine-fausse"),
            pytest.param(1, id="entier"),
            pytest.param(0, id="zero"),
            pytest.param({"actif": True}, id="objet"),
        ],
    )
    def test_une_valeur_douteuse_retombe_sur_le_defaut(self, stored):
        """Un réglage se saisit à la main : il peut contenir n'importe quoi."""
        AppSetting.objects.create(key="ai_enabled", value=stored)

        assert AppSetting.get_bool("ai_enabled", default=True) is True
        assert AppSetting.get_bool("ai_enabled", default=False) is False

    def test_le_reglage_est_relu_a_chaque_appel(self):
        """Un coupe-circuit agit à l'instant où on l'actionne (spec 07 §11)."""
        setting = AppSetting.objects.create(key="ai_enabled", value=True)
        assert AppSetting.get_bool("ai_enabled", default=True) is True

        setting.value = False
        setting.save(update_fields=["value"])

        assert AppSetting.get_bool("ai_enabled", default=True) is False
