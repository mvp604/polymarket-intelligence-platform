import unittest

from src.runtime import ServiceContainer


class DummyService:
    pass


class ServiceContainerTests(unittest.TestCase):

    def test_register_and_resolve(self):
        container = ServiceContainer()
        service = DummyService()

        container.register(DummyService, service)

        self.assertIs(
            container.resolve(DummyService),
            service,
        )

    def test_contains(self):
        container = ServiceContainer()

        self.assertFalse(
            container.contains(DummyService)
        )

        container.register(
            DummyService,
            DummyService(),
        )

        self.assertTrue(
            container.contains(DummyService)
        )

    def test_overwrite_registration(self):
        container = ServiceContainer()

        first = DummyService()
        second = DummyService()

        container.register(DummyService, first)
        container.register(DummyService, second)

        self.assertIs(
            container.resolve(DummyService),
            second,
        )


if __name__ == "__main__":
    unittest.main()
