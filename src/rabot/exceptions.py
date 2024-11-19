class RabotError(Exception):
    """This is our fault. Sorry."""


class FetchError(Exception):
    """Generic error while fetching some site."""


class NotFoundError(Exception):
    """Delete me please."""
