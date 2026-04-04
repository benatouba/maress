"""NLP module logger.

All NLP sub-modules import ``logger`` from here.  The actual handler/format
configuration is done by ``app.core.logging.setup_logging()`` on the root
logger, so this file only needs to create a namespaced child logger.
"""

import logging

logger = logging.getLogger("app.nlp")
