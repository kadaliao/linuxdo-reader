from collections.abc import Iterator

import pytest

from linuxdo_reader.storage import Store


@pytest.fixture(autouse=True)
def close_test_stores(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    stores: list[Store] = []
    original_init = Store.__init__

    def tracked_init(self: Store, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        stores.append(self)

    monkeypatch.setattr(Store, "__init__", tracked_init)
    yield
    for store in reversed(stores):
        store.close()
