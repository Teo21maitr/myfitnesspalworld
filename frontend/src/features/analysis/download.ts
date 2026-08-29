/**
 * Remise d'un fichier au navigateur.
 *
 * Le backend répond un `Blob`, pas une URL : un lien direct vers l'API
 * n'emporterait pas les cookies d'authentification dans tous les navigateurs,
 * et exposerait une route de données privées à un simple clic droit.
 */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()

  // Libère l'objet : sans cela le Blob vit jusqu'au rechargement de la page.
  URL.revokeObjectURL(url)
}

/** Nom de fichier d'un export, aligné sur celui que propose le backend. */
export function reportFilename(format: string, from: string, to: string): string {
  const compact = (iso: string) => iso.replaceAll('-', '')
  return `myfitnesspalworld-${compact(from)}-${compact(to)}.${format}`
}
