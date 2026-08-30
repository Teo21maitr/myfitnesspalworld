"""Traitement d'une image avant stockage (spec 01 §20, spec 05 §10).

L'EXIF est le point sensible. Un cliché de téléphone porte les coordonnées GPS
du lieu où il a été pris, et une photo de progression est prise chez soi. Le
client compresse déjà de son côté — ce qui retire l'EXIF au passage — mais le
frontend n'est jamais la source de vérité (CLAUDE.md §2) : un autre client
enverrait l'original.
"""

import io

import pytest
from PIL import Image

from progress.services.photos import MAX_SIDE, prepare


def jpeg(size=(60, 40), *, exif=None, color=(120, 30, 30)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", **({"exif": exif} if exif else {}))
    return buffer.getvalue()


def geotagged() -> bytes:
    """Un JPEG portant une marque d'appareil et des coordonnées GPS."""
    image = Image.new("RGB", (60, 40), (10, 90, 40))
    exif = image.getexif()
    exif[271] = "TestPhone"
    exif[34853] = {1: "N", 2: (48.0, 51.0, 24.0)}
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def read(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


class TestExifIsStripped:
    def test_les_coordonnees_gps_disparaissent(self):
        stored = prepare(geotagged())

        with read(stored) as image:
            assert dict(image.getexif()) == {}

    def test_la_marque_de_l_appareil_disparait(self):
        source = geotagged()
        with read(source) as before:
            assert before.getexif().get(271) == "TestPhone"

        with read(prepare(source)) as after:
            assert after.getexif().get(271) is None

    def test_une_image_sans_exif_reste_valide(self):
        stored = prepare(jpeg())

        with read(stored) as image:
            assert image.format == "JPEG"
            assert image.size == (60, 40)


class TestResizing:
    def test_une_image_trop_grande_est_reduite(self):
        stored = prepare(jpeg((4000, 3000)))

        with read(stored) as image:
            assert max(image.size) == MAX_SIDE
            # Les proportions sont conservées : 4/3 reste 4/3.
            assert image.size == (MAX_SIDE, int(MAX_SIDE * 3 / 4))

    def test_une_petite_image_n_est_pas_agrandie(self):
        stored = prepare(jpeg((320, 240)))

        with read(stored) as image:
            assert image.size == (320, 240)

    def test_le_resultat_pese_moins_que_l_original(self):
        source = jpeg((4000, 3000))

        assert len(prepare(source)) < len(source)


class TestFormats:
    @pytest.mark.parametrize("source_format", ["PNG", "WEBP"])
    def test_tout_ressort_en_jpeg(self, source_format):
        """Un seul format à servir, et le réencodage fait tomber le reste."""
        buffer = io.BytesIO()
        Image.new("RGB", (50, 50), (200, 200, 0)).save(buffer, format=source_format)

        with read(prepare(buffer.getvalue())) as image:
            assert image.format == "JPEG"

    def test_une_image_avec_transparence_ne_casse_pas(self):
        buffer = io.BytesIO()
        Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(buffer, format="PNG")

        with read(prepare(buffer.getvalue())) as image:
            assert image.mode == "RGB"


def test_une_image_de_la_taille_maximale_reste_synchrone():
    """La mesure décide, pas l'intuition (spec 07 §9).

    Une image à la limite d'envoi se traite en une fraction de seconde : rien
    ne justifie de passer par Celery, et l'utilisateur doit voir son résultat.
    Ce test échouera le jour où ce ne sera plus vrai.
    """
    import time

    from PIL import Image

    grande = Image.new("RGB", (5200, 3900))
    grande.putdata(
        [(index % 256, (index * 7) % 256, (index * 13) % 256) for index in range(80_000)]
    )
    buffer = io.BytesIO()
    grande.save(buffer, format="JPEG", quality=95)

    début = time.perf_counter()
    prepare(buffer.getvalue())
    durée = time.perf_counter() - début

    assert durée < 2.0, f"{durée:.2f} s : le traitement mérite de passer en asynchrone"
