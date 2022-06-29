from radiofeed.common.utils import batcher


class TestBatcher:
    def test_batcher(self):
        batches = list(batcher(range(0, 100), batch_size=10))
        assert len(batches) == 10
        assert batches[0] == list(range(0, 10))
