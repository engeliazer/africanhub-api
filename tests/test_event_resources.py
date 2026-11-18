"""HTTP contract tests for event zip resources (admin + attendance-number public)."""
import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

ROOT = Path(__file__).resolve().parents[1]


def module_stub(name, **values):
    module = types.ModuleType(name)
    module.__dict__.update(values)
    return module


class EventResourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        event_model = MagicMock()
        stubs = {
            "database.db_connector": module_stub("database.db_connector", get_db=MagicMock()),
            "events.models.models": module_stub(
                "events.models.models",
                Event=event_model,
                EventResource=MagicMock(),
            ),
            "events.services.event_resource_service": module_stub(
                "events.services.event_resource_service",
                absolute_resource_path=MagicMock(),
                attendance_number_from_request=MagicMock(),
                create_event_resource=MagicMock(),
                get_active_resource=MagicMock(),
                list_active_resources=MagicMock(),
                resolve_event_by_attendance_number=MagicMock(),
                resource_download_name=MagicMock(return_value="pack.zip"),
                resource_to_dict=MagicMock(),
                soft_delete_event_resource=MagicMock(),
            ),
        }
        spec = importlib.util.spec_from_file_location(
            "event_resources_test_controller",
            ROOT / "events/controllers/event_resources_controller.py",
        )
        cls.controller = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, stubs):
            spec.loader.exec_module(cls.controller)

        app = Flask(__name__)
        app.config["JWT_SECRET_KEY"] = "test-secret-key-for-event-resources"
        JWTManager(app)
        with app.app_context():
            cls.auth_headers = {
                "Authorization": "Bearer " + create_access_token(identity="9"),
            }
        app.register_blueprint(cls.controller.event_resources_bp)
        cls.client = app.test_client()
        cls.service = cls.controller

    def setUp(self):
        self.db = MagicMock()
        self.controller.get_db.return_value = self.db
        self.event = types.SimpleNamespace(
            id=7,
            title="November Training",
            course_title="Python Fundamentals",
            venue="Dar",
            start_date=date(2026, 11, 13),
            end_date=date(2026, 11, 14),
        )
        self.resource = types.SimpleNamespace(
            id=3,
            event_id=7,
            name="Handouts",
            description="Pack",
            extension_type="zip",
            file_size=100,
            created_at=None,
            updated_at=None,
            serial_no=None,
        )
        event_query = MagicMock()
        event_query.filter.return_value.first.return_value = self.event
        self.db.query.return_value = event_query

        self.controller.list_active_resources.reset_mock()
        self.controller.create_event_resource.reset_mock()
        self.controller.resolve_event_by_attendance_number.reset_mock()
        self.controller.get_active_resource.reset_mock()
        self.controller.resource_to_dict.reset_mock()
        self.controller.attendance_number_from_request.reset_mock()
        self.controller.absolute_resource_path.reset_mock()
        self.controller.soft_delete_event_resource.reset_mock()

    def test_admin_list_requires_auth(self):
        response = self.client.get("/api/events/7/resources")
        self.assertEqual(response.status_code, 401)

    def test_admin_list_resources(self):
        self.controller.list_active_resources.return_value = [self.resource]
        self.controller.resource_to_dict.return_value = {"id": 3, "name": "Handouts"}

        response = self.client.get(
            "/api/events/7/resources",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["total"], 1)
        self.assertEqual(body["data"]["resources"][0]["id"], 3)
        self.controller.list_active_resources.assert_called_once_with(self.db, 7)
        self.db.close.assert_called_once()

    def test_public_list_by_attendance_number(self):
        participant = types.SimpleNamespace(serial_no="AH/ORG/CODE/AB12")
        context = types.SimpleNamespace(subject_title="Python Fundamentals")
        self.controller.attendance_number_from_request.return_value = "AH/ORG/CODE/AB12"
        self.controller.resolve_event_by_attendance_number.return_value = (
            self.event,
            participant,
            context,
            "CPA. Asha Mushi",
            None,
        )
        self.controller.list_active_resources.return_value = [self.resource]
        self.controller.resource_to_dict.return_value = {
            "id": 3,
            "download_url": "/api/events/public/resources/3/download?attendance_number=AH%2FORG%2FCODE%2FAB12",
        }

        response = self.client.get(
            "/api/events/public/resources?attendance_number=AH/ORG/CODE/AB12"
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"]["attendance_number"], "AH/ORG/CODE/AB12")
        self.assertEqual(body["data"]["participant_name"], "CPA. Asha Mushi")
        self.assertEqual(body["data"]["event"]["id"], 7)
        self.assertEqual(body["data"]["resource_count"], 1)

    def test_public_list_unknown_attendance_number(self):
        self.controller.attendance_number_from_request.return_value = "missing"
        self.controller.resolve_event_by_attendance_number.return_value = (
            None, None, None, None, "Attendance number not found",
        )
        response = self.client.get("/api/events/public/resources?attendance_number=missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Attendance number not found")

    def test_public_download_missing_resource(self):
        self.controller.attendance_number_from_request.return_value = "AH/ORG/CODE/AB12"
        self.controller.resolve_event_by_attendance_number.return_value = (
            self.event,
            types.SimpleNamespace(serial_no="AH/ORG/CODE/AB12"),
            types.SimpleNamespace(subject_title="Python"),
            "Asha",
            None,
        )
        self.controller.get_active_resource.return_value = None

        response = self.client.get(
            "/api/events/public/resources/99/download?attendance_number=AH/ORG/CODE/AB12"
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Resource not found")

    def test_admin_delete_resource(self):
        self.controller.get_active_resource.return_value = self.resource
        response = self.client.delete(
            "/api/events/7/resources/3",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.controller.soft_delete_event_resource.assert_called_once()
        args = self.controller.soft_delete_event_resource.call_args.args
        self.assertIs(args[0], self.db)
        self.assertIs(args[1], self.resource)
        self.assertEqual(args[2], 9)


if __name__ == "__main__":
    unittest.main()