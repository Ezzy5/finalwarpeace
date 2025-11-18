from .. import bp

@bp.route("/favicon.ico")
def favicon():
    return "", 204
