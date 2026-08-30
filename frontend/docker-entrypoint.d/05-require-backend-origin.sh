#!/bin/sh
# Refuse de démarrer sans `BACKEND_ORIGIN`, en le disant.
#
# `envsubst` ne remplace que les variables présentes dans l'environnement :
# absente, `${BACKEND_ORIGIN}` traverse le gabarit intacte, et nginx la prend
# pour une de ses propres variables. Le message obtenu — « unknown
# "backend_origin" variable » — ne nomme ni la variable à poser, ni ce qu'elle
# sert. Ce script s'exécute avant `20-envsubst-on-templates.sh` et le dit.
set -e

if [ -z "${BACKEND_ORIGIN}" ]; then
    echo "BACKEND_ORIGIN est obligatoire : nginx relaie /api/ vers cette" >&2
    echo "adresse, ce qui met l'API sous la même origine que l'application." >&2
    echo "Sans cela le cookie de session serait un cookie tiers, que Safari" >&2
    echo "bloque — l'application marcherait sur ordinateur et pas sur mobile." >&2
    echo "Exemple : BACKEND_ORIGIN=https://mon-backend.exemple.com" >&2
    exit 1
fi

case "${BACKEND_ORIGIN}" in
    */)
        echo "BACKEND_ORIGIN ne doit pas se terminer par « / » : nginx" >&2
        echo "retirerait alors /api/ du chemin transmis, et le backend" >&2
        echo "répondrait 404 à chaque appel." >&2
        exit 1
        ;;
esac
