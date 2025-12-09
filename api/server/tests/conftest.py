"""Pytest configuration and fixtures for tests."""

import os
import sys
import types
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

import pytest


# Ensure `server/` is importable when tests reference `app`
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_path not in sys.path:
    sys.path.insert(0, src_path)


QUIZ_SAMPLE_DOCS: List[Dict[str, Any]] = [
    {
        "topic": "Containers",
        "subtopic": "Basics",
        "keywords": ["Docker", "Podman"],
        "style_modifiers": ["concept explanation", "use case scenario"],
    },
    {
        "topic": "Containers",
        "subtopic": "Advanced",
        "keywords": ["Kubernetes", "Service Mesh"],
        "style_modifiers": ["comparison", "troubleshooting"],
    },
    {
        "topic": "CI/CD",
        "subtopic": "Basics",
        "keywords": ["Pipelines", "Automation"],
        "style_modifiers": ["concept explanation"],
    },
]


def _matches(document: Dict[str, Any], filter_query: Dict[str, Any]) -> bool:
    if not filter_query:
        return True
    for key, expected in filter_query.items():
        if document.get(key) != expected:
            return False
    return True


class _InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _UpdateResult:
    def __init__(self, matched: int, modified: int):
        self.matched_count = matched
        self.modified_count = modified


class FakeCollection:
    """Minimal PyMongo-like collection for deterministic unit tests."""

    def __init__(self, documents: Iterable[Dict[str, Any]]):
        self._documents: List[Dict[str, Any]] = [deepcopy(doc) for doc in documents]
        self._id_counter = 1

    def _ensure_id(self, document: Dict[str, Any]) -> Dict[str, Any]:
        doc = deepcopy(document)
        if "_id" not in doc:
            doc["_id"] = str(self._id_counter)
            self._id_counter += 1
        return doc

    def distinct(self, field: str, filter_query: Optional[Dict[str, Any]] = None):
        docs = [doc for doc in self._documents if _matches(doc, filter_query or {})]
        values = []
        for doc in docs:
            value = doc.get(field)
            if isinstance(value, list):
                values.extend(value)
            elif value is not None:
                values.append(value)
        # Preserve insertion order while removing duplicates
        seen = set()
        ordered = []
        for value in values:
            if value not in seen:
                ordered.append(value)
                seen.add(value)
        return ordered

    def find_one(self, filter_query: Dict[str, Any]):
        for doc in self._documents:
            if _matches(doc, filter_query):
                return deepcopy(doc)
        return None

    def find(self, filter_query: Optional[Dict[str, Any]] = None):
        return [
            deepcopy(doc) for doc in self._documents if _matches(doc, filter_query or {})
        ]

    def insert_one(self, document: Dict[str, Any]):
        doc = self._ensure_id(document)
        self._documents.append(doc)
        return _InsertOneResult(doc["_id"])

    # Methods invoked by import/migration paths; implemented as no-ops.
    def delete_many(self, _filter: Dict[str, Any]):
        self._documents.clear()

    def insert_many(self, docs: Iterable[Dict[str, Any]]):
        for doc in docs:
            self._documents.append(self._ensure_id(doc))

    def update_one(self, filter_query: Dict[str, Any], update_doc: Dict[str, Any]):
        matched = 0
        modified = 0
        for doc in self._documents:
            if _matches(doc, filter_query):
                matched += 1
                modified += self._apply_update(doc, update_doc)
                break
        return _UpdateResult(matched, modified)

    def _apply_update(self, document: Dict[str, Any], update_doc: Dict[str, Any]) -> int:
        modified = 0
        if "$set" in update_doc:
            for key, value in update_doc["$set"].items():
                if document.get(key) != value:
                    document[key] = value
                    modified += 1
        if "$inc" in update_doc:
            for key, value in update_doc["$inc"].items():
                document[key] = document.get(key, 0) + value
                modified += 1
        return modified


class FakeMongoDatabase:
    """Dictionary-like facade returning fake collections by name."""

    def __init__(self):
        self._collections: Dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self._collections:
            initial_docs = QUIZ_SAMPLE_DOCS if name == "quiz_data" else []
            self._collections[name] = FakeCollection(initial_docs)
        return self._collections[name]


def _patch_db_controller() -> None:
    """Replace DBController.connect with in-memory stub for tests."""

    from common import database as database_module

    original_class = database_module.DBController

    class _FakeDBController(original_class):  # type: ignore[misc]
        def connect(self) -> bool:  # pragma: no cover - exercised via app factory
            self.client = None
            self.db = FakeMongoDatabase()
            return True

    database_module.DBController = _FakeDBController


_patch_db_controller()


def _patch_authlib() -> None:
    """Provide a fake authlib OAuth client for unit tests."""

    class _FakeOAuth:
        def init_app(self, _app):  # pragma: no cover - simple stub
            return None

        def register(self, **_kwargs):  # pragma: no cover - simple stub
            return None

    authlib_module = types.ModuleType("authlib")
    integrations_module = types.ModuleType("authlib.integrations")
    flask_client_module = types.ModuleType("authlib.integrations.flask_client")
    flask_client_module.OAuth = _FakeOAuth
    integrations_module.flask_client = flask_client_module
    authlib_module.integrations = integrations_module

    sys.modules["authlib"] = authlib_module
    sys.modules["authlib.integrations"] = integrations_module
    sys.modules["authlib.integrations.flask_client"] = flask_client_module


_patch_authlib()


def _patch_prometheus() -> None:
    """Provide a fake Prometheus metrics exporter for tests."""

    class _FakePrometheusMetrics:
        def __init__(self, _app=None, *args, **kwargs):  # pragma: no cover
            self._app = _app

        def info(self, *_args, **_kwargs):  # pragma: no cover
            return None

    prom_module = types.ModuleType("prometheus_flask_exporter")
    prom_module.PrometheusMetrics = _FakePrometheusMetrics
    sys.modules["prometheus_flask_exporter"] = prom_module


_patch_prometheus()


@pytest.fixture(scope="session")
def app_instance():
    """Create the Flask app once for all tests using the real factory."""

    # Import here so our fakes above take effect before modules load
    from app import create_app  # pylint: disable=import-outside-toplevel

    application = create_app()
    application.config["TESTING"] = True
    yield application


@pytest.fixture()
def client(app_instance):
    """Provide a test client bound to the shared application."""

    with app_instance.test_client() as client:
        yield client
