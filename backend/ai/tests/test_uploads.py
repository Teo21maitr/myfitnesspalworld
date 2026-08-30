"""Validation des images reçues (spec 05 §14)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from ai.services.uploads import MAX_IMAGES, read_uploads

from .conftest import JPEG_BYTES, PNG_BYTES

WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 32


def upload(content: bytes, content_type: str = "image/jpeg", name: str = "repas.jpg"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class TestAcceptedFormats:
    @pytest.mark.parametrize(
        ("content", "content_type", "name"),
        [
            pytest.param(JPEG_BYTES, "image/jpeg", "repas.jpg", id="jpeg"),
            pytest.param(PNG_BYTES, "image/png", "repas.png", id="png"),
            pytest.param(WEBP_BYTES, "image/webp", "repas.webp", id="webp"),
        ],
    )
    def test_une_image_valide_est_acceptee(self, content, content_type, name):
        images = read_uploads([upload(content, content_type, name)])

        assert len(images) == 1
        assert images[0].media_type == content_type
        assert images[0].data == content

    def test_le_parametre_de_charset_est_ignore(self):
        images = read_uploads([upload(JPEG_BYTES, "image/jpeg; charset=binary")])

        assert images[0].media_type == "image/jpeg"


class TestRefusals:
    def test_aucun_fichier(self):
        with pytest.raises(ValidationError):
            read_uploads([])

    def test_trop_de_fichiers(self):
        with pytest.raises(ValidationError):
            read_uploads([upload(JPEG_BYTES) for _ in range(MAX_IMAGES + 1)])

    def test_format_non_supporte(self):
        with pytest.raises(ValidationError):
            read_uploads([upload(b"%PDF-1.4", "application/pdf", "repas.pdf")])

    def test_le_type_declare_ne_suffit_pas(self):
        """Un client peut annoncer ce qu'il veut : le contenu est vérifié."""
        with pytest.raises(ValidationError):
            read_uploads([upload(b"MZ\x90\x00 pas une image", "image/jpeg")])

    def test_un_png_annonce_en_jpeg_est_refuse(self):
        with pytest.raises(ValidationError):
            read_uploads([upload(PNG_BYTES, "image/jpeg")])

    def test_fichier_trop_volumineux(self, settings):
        settings.MAX_UPLOAD_SIZE_MB = 1
        oversized = JPEG_BYTES + b"\x00" * (1024 * 1024)

        with pytest.raises(ValidationError):
            read_uploads([upload(oversized)])


def test_une_extension_qui_contredit_le_type_est_refusee():
    """Un renommage trahit une intention, et rien de bon ne commence par là."""
    with pytest.raises(ValidationError):
        read_uploads([upload(PNG_BYTES, "image/png", "photo.jpg")])


def test_une_extension_en_majuscules_est_acceptee():
    images = read_uploads([upload(JPEG_BYTES, "image/jpeg", "PHOTO.JPG")])

    assert len(images) == 1
