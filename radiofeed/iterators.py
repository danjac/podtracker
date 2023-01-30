from __future__ import annotations

import itertools

from collections.abc import Iterable


def chunked_iterator(iterable: Iterable, batch_size: int) -> Iterable[list]:
    """Batches an iterable into lists of given batch size.

    Useful for handling long iterables where individual processing might be slow.
    """
    iterator = iter(iterable)
    while batch := list(itertools.islice(iterator, batch_size)):
        yield batch
