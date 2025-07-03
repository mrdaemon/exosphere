import lzma
import pickle
import shelve


class DiskCache(shelve.DbfilenameShelf):
    """
    Shelf-based disk cache with LZMA compression persistence

    This class wraps `shelve.DbfilenameShelf` to provide lzma
    compression, but does not otherwise change the interface.
    Would recommend not using writeback=True given the overhead.
    Doing so is also entirely untested, so good luck.
    """

    def __getitem__(self, key):
        value = super().__getitem__(key)
        return pickle.loads(lzma.decompress(value))

    def __setitem__(self, key, value):
        compressed_value = lzma.compress(
            pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        )
        super().__setitem__(key, compressed_value)

    # We also override the get method to ensure it goes through
    # our compressed __getitem__ method, otherwise the parent get
    # would absolutely return a raw compressed blob.
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
