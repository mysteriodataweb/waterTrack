/**
 * Copie un texte dans le presse-papiers. Repli sur l'ancienne méthode quand le
 * presse-papiers moderne est indisponible (page servie sans https).
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    let done = false;
    try { done = document.execCommand("copy"); } catch { done = false; }
    field.remove();
    return done;
  }
}
