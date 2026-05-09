# Import all tool modules so their @REGISTRY.tool decorators fire on first import
from sage.tools import (  # noqa: F401
    file_tools,
    git_tools,
    retrieval_tools,
    search_tools,
    shell_tools,
)
from sage.tools.registry import REGISTRY  # noqa: F401
