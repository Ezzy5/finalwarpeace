# app/tickets/routes/__init__.py
"""
Routes package for tickets.

Each submodule imports the shared Blueprint `bp` from app.tickets.__init__
and registers its own routes via decorators. Importing these modules here
ensures the routes are registered when the package is imported.
"""

# Make sure modules can do: `from .. import bp`
from .. import bp  # noqa: F401

# Import submodules so their route decorators execute
from .panel import *       # noqa: F401,F403
from .create import *      # noqa: F401,F403
from .view import *        # noqa: F401,F403
from .edit import *        # noqa: F401,F403
from .checklist import *   # noqa: F401,F403
from .comments import *    # noqa: F401,F403
from .status import *      # noqa: F401,F403
from .files import *       # noqa: F401,F403
from .complete import *    # noqa: F401,F403
