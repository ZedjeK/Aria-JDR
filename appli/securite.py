"""Ce qui garde l'interface locale : elle ne s'ouvre que par l'appli.

Le serveur n'écoute que sur 127.0.0.1. En plus :

- l'en-tête Host doit être 127.0.0.1:<port> ou localhost:<port> (un site qui se ferait passer pour 127.0.0.1 pour lire
  les données de l'appli, le « DNS rebinding », est refusé) ;
- l'en-tête Origin, quand il est présent, doit être celui de l'appli (une autre page ouverte dans le navigateur ne peut
  pas agir sur elle) ;
- un jeton tiré au hasard à chaque lancement est exigé à chaque requête. Il passe une seule fois dans l'adresse
  d'ouverture (/?j=jeton) ; le serveur le met alors dans un cookie réservé à l'appli (HttpOnly, SameSite=Strict) et
  redirige vers /, sans le jeton ;
- aucune action ne passe par un GET, et aucun CORS n'est ouvert.
"""

import secrets

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

from appli import identite

COOKIE = f"{identite.EXE.lower().replace('-', '_')}_jeton"

_ENTETES = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
}


def nouveau_jeton() -> str:
    return secrets.token_urlsafe(32)


def installer(app: FastAPI, port: int, jeton: str) -> None:
    """Pose le contrôle sur toutes les requêtes de l'appli."""
    hotes = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origines = {f"http://{h}" for h in hotes}

    def refuser(code: int, texte: str) -> Response:
        return PlainTextResponse(texte, status_code=code, headers=_ENTETES)

    @app.middleware("http")
    async def garder(request: Request, call_next):
        if request.headers.get("host") not in hotes:
            return refuser(403, "Hôte refusé.")
        origine = request.headers.get("origin")
        if origine is not None and origine not in origines:
            return refuser(403, "Origine refusée.")

        propose = request.query_params.get("j")
        if request.url.path == "/" and propose is not None:
            if not secrets.compare_digest(propose, jeton):
                return refuser(403, "Jeton refusé.")
            reponse = RedirectResponse("/", status_code=303, headers=_ENTETES)
            reponse.set_cookie(COOKIE, jeton, httponly=True, samesite="strict", path="/")
            return reponse

        cookie = request.cookies.get(COOKIE, "")
        if not secrets.compare_digest(cookie, jeton):
            return refuser(403, f"Ouvre {identite.NOM} par son exe : l'interface ne s'ouvre que par l'appli.")

        reponse = await call_next(request)
        for nom, valeur in _ENTETES.items():
            reponse.headers.setdefault(nom, valeur)
        return reponse
