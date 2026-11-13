"""Isolated HTTP contract tests; database and campaign PDF renderer are mocked."""
import importlib.util
import sys
import tempfile
import types
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

ROOT = Path(__file__).resolve().parents[1]


def module_stub(name, **values):
    module = types.ModuleType(name)
    module.__dict__.update(values)
    return module


class FakeIntegrityError(Exception):
    def __init__(self, orig):
        super().__init__(orig)
        self.orig = orig


class PublicInvitationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load only this controller, without app.py's external service setup.
        invitation_model = MagicMock()
        event_model = MagicMock()
        stubs = {
            "applications.models.models": module_stub(
                "applications.models.models", Invitation=invitation_model,
                InvitationCampaignStatus=types.SimpleNamespace(cancelled="CANCELLED"),
            ),
            "events.models.models": module_stub(
                "events.models.models", Event=event_model, EventTrainingRegistration=MagicMock(),
            ),
            "sqlalchemy.exc": module_stub("sqlalchemy.exc", IntegrityError=FakeIntegrityError),
            "database.db_connector": module_stub("database.db_connector", get_db=MagicMock()),
            "public.services.invitation_campaign_pdf_service": module_stub(
                "public.services.invitation_campaign_pdf_service", render_invitation_pdf_bytes=MagicMock(),
            ),
        }
        spec = importlib.util.spec_from_file_location(
            "public_invitation_test_controller", ROOT / "public/controllers/public_invitations_controller.py"
        )
        cls.controller = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, stubs):
            spec.loader.exec_module(cls.controller)
        app = Flask(__name__)
        app.config["JWT_SECRET_KEY"] = "test-secret-key-for-registration-tests"
        JWTManager(app)
        with app.app_context():
            cls.auth_headers = {"Authorization": "Bearer " + create_access_token(identity="1")}
        app.register_blueprint(cls.controller.public_invitations_bp)
        cls.client = app.test_client()

    def setUp(self):
        self.db = MagicMock()
        self.invitation = types.SimpleNamespace(
            id=20, additional_attachment_path=None, additional_attachment_filename=None,
        )
        self.event_query = MagicMock()
        self.event_query.filter.return_value.first.return_value = types.SimpleNamespace(id=7)
        self.invitation_query = MagicMock()
        self.invitation_query.filter.return_value.order_by.return_value.first.return_value = self.invitation
        self.db.query.side_effect = [self.event_query, self.invitation_query]
        self.controller.get_db.return_value = self.db
        self.controller.render_invitation_pdf_bytes.reset_mock()
        self.controller.render_invitation_pdf_bytes.side_effect = None
        self.controller.render_invitation_pdf_bytes.return_value = (b"%PDF-test-letter", "Invitation_Asha.pdf")
        self.payload = dict(first_name=" Asha ", middle_name="Juma", last_name="Mushi",
                            email="asha@example.com", phone="+255 712 345 678",
                            address="P.O. Box 123", organization="Example Ltd")
        self.url = "/api/events/public/7/self-invitation"
        self.attachment_url = "/api/events/public/7/invitation/attachment"

    def test_self_invitation_without_auth_uses_campaign_renderer(self):
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, b"%PDF-test-letter")
        self.assertTrue(response.headers["Content-Disposition"].startswith("inline;"))
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        invitation, invitee = self.controller.render_invitation_pdf_bytes.call_args.args
        self.assertIs(invitation, self.invitation)
        self.assertEqual(invitee["full_name"], "Asha Juma Mushi")
        self.assertEqual(invitee["phone"], "+255712345678")
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()

    def test_invalid_payloads(self):
        for data in [None, [], "text", 123, {}, *[
            dict(self.payload, **{field: value})
            for field, value in [("first_name", ""), ("middle_name", None), ("last_name", 123),
                                 ("email", "bad"), ("phone", "123"), ("phone", "abc1234567"),
                                 ("organization", "x" * 256), ("address", " ")]
        ]]:
            with self.subTest(data=data):
                response = self.client.post(self.url, json=data)
                self.assertEqual(response.status_code, 400)
        self.controller.render_invitation_pdf_bytes.assert_not_called()

    def test_malformed_json(self):
        response = self.client.post(self.url, data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_hidden_or_missing_event(self):
        self.event_query.filter.return_value.first.return_value = None
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.query.call_count, 1)
        self.controller.Event.is_published.is_.assert_called_with(True)
        self.controller.render_invitation_pdf_bytes.assert_not_called()
        self.db.close.assert_called_once()

    def test_missing_invitation(self):
        self.invitation_query.filter.return_value.order_by.return_value.first.return_value = None
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 404)
        self.controller.Invitation.event_id.__eq__.assert_called_with(7)
        self.controller.Invitation.status.__ne__.assert_called_with("CANCELLED")
        self.controller.Invitation.id.desc.assert_called()

    def test_renderer_failure_closes_session(self):
        self.controller.render_invitation_pdf_bytes.side_effect = RuntimeError("internal detail")
        with self.assertLogs(self.controller.logger, level="ERROR"):
            response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"internal detail", response.data)
        self.db.close.assert_called_once()

    def test_attachment_without_auth_is_inline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attachment.pdf"
            path.write_bytes(b"%PDF-test-attachment")
            self.invitation.additional_attachment_path = str(path)
            self.invitation.additional_attachment_filename = "Course contents.pdf"
            response = self.client.get(self.attachment_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "application/pdf")
            self.assertEqual(response.data, b"%PDF-test-attachment")
            self.assertIn('inline;', response.headers["Content-Disposition"])
            self.assertIn('Course contents.pdf', response.headers["Content-Disposition"])
            response.close()
        self.db.close.assert_called_once()

    def test_absent_or_missing_attachment(self):
        for path in [None, "/nonexistent/attachment.pdf"]:
            with self.subTest(path=path):
                self.db.query.side_effect = [self.event_query, self.invitation_query]
                self.invitation.additional_attachment_path = path
                response = self.client.get(self.attachment_url)
                self.assertEqual(response.status_code, 404)

    def test_attachment_hidden_event(self):
        self.event_query.filter.return_value.first.return_value = None
        self.assertEqual(self.client.get(self.attachment_url).status_code, 404)
        self.assertEqual(self.db.query.call_count, 1)


    def test_registration_is_pending_and_persists_details(self):
        registration = types.SimpleNamespace(id=42, status="pending")
        self.controller.EventTrainingRegistration.return_value = registration
        payload = dict(self.payload, status="paid", email="ASHA@example.com")
        response = self.client.post("/api/events/public/7/registrations", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["data"], {"id": 42, "event_id": 7, "status": "pending"})
        fields = self.controller.EventTrainingRegistration.call_args.kwargs
        self.assertEqual(fields["status"], "pending")
        self.assertEqual(fields["email"], "asha@example.com")
        self.assertEqual(fields["first_name"], "Asha")
        self.assertEqual(fields["phone"], "+255712345678")
        self.assertEqual(fields["address"], self.payload["address"])
        self.db.add.assert_called_once_with(registration)
        self.db.commit.assert_called_once()
        self.db.close.assert_called_once()
        self.assertEqual(self.db.query.call_count, 1)
        self.controller.render_invitation_pdf_bytes.assert_not_called()

    def test_list_registrations_requires_jwt(self):
        response = self.client.get("/api/events/7/registrations")
        self.assertEqual(response.status_code, 401)
        self.db.query.assert_not_called()

    def test_registration_summary_requires_jwt(self):
        response = self.client.get("/api/events/registrations")
        self.assertEqual(response.status_code, 401)
        self.db.query.assert_not_called()

    def test_registration_summary_includes_events_without_signups(self):
        events = [
            (types.SimpleNamespace(id=7, title="Training", course_title="Python",
                                   start_date=date(2026, 11, 13), end_date=date(2026, 11, 14),
                                   is_published=True), 3),
            (types.SimpleNamespace(id=6, title="Draft", course_title="SQL",
                                   start_date=None, end_date=None, is_published=False), 0),
        ]
        query = self.invitation_query.outerjoin.return_value.order_by.return_value
        query.all.return_value = events
        response = self.client.get("/api/events/registrations", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"], {
            "total_events": 2, "total_registrations": 3,
            "events": [
                {"event_id": 7, "title": "Training", "course_title": "Python",
                 "start_date": "2026-11-13", "end_date": "2026-11-14",
                 "is_published": True, "registration_count": 3},
                {"event_id": 6, "title": "Draft", "course_title": "SQL",
                 "start_date": None, "end_date": None,
                 "is_published": False, "registration_count": 0},
            ],
        })
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.db.close.assert_called_once()

    def test_registration_summary_empty(self):
        self.invitation_query.outerjoin.return_value.order_by.return_value.all.return_value = []
        response = self.client.get("/api/events/registrations", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"], {
            "total_events": 0, "total_registrations": 0, "events": [],
        })

    def test_registration_summary_database_failure(self):
        self.db.query.side_effect = RuntimeError("private database detail")
        with self.assertLogs(self.controller.logger, level="ERROR"):
            response = self.client.get("/api/events/registrations", headers=self.auth_headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"private database detail", response.data)
        self.db.close.assert_called_once()

    def test_list_registrations_rejects_invalid_jwt(self):
        response = self.client.get("/api/events/7/registrations",
                                   headers={"Authorization": "Bearer invalid"})
        self.assertEqual(response.status_code, 422)
        self.db.query.assert_not_called()

    def test_list_registrations_returns_website_details(self):
        row = types.SimpleNamespace(
            id=42, event_id=7, status="pending", created_at=datetime(2026, 11, 13, 10),
            updated_at=None, **self.payload,
        )
        self.invitation_query.filter.return_value.order_by.return_value.all.return_value = [row]
        response = self.client.get("/api/events/7/registrations", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json["data"]
        self.assertEqual(data["event_id"], 7)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["registrations"], [dict(
            self.payload, id=42, event_id=7, status="pending",
            created_at="2026-11-13T10:00:00", updated_at=None,
        )])
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertEqual(len(self.event_query.filter.call_args.args), 1)
        self.controller.EventTrainingRegistration.event_id.__eq__.assert_called_with(7)
        self.db.close.assert_called_once()

    def test_list_registrations_empty(self):
        self.invitation_query.filter.return_value.order_by.return_value.all.return_value = []
        response = self.client.get("/api/events/7/registrations", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"], {"event_id": 7, "total": 0, "registrations": []})

    def test_list_registrations_missing_event(self):
        self.event_query.filter.return_value.first.return_value = None
        response = self.client.get("/api/events/7/registrations", headers=self.auth_headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.query.call_count, 1)
        self.db.close.assert_called_once()

    def test_list_registrations_database_failure(self):
        self.db.query.side_effect = RuntimeError("private database detail")
        with self.assertLogs(self.controller.logger, level="ERROR"):
            response = self.client.get("/api/events/7/registrations", headers=self.auth_headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"private database detail", response.data)
        self.db.close.assert_called_once()

    def test_registration_rejects_invalid_details(self):
        response = self.client.post("/api/events/public/7/registrations", json=dict(self.payload, phone="bad"))
        self.assertEqual(response.status_code, 400)
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()

    def test_registration_requires_published_event(self):
        self.event_query.filter.return_value.first.return_value = None
        response = self.client.post("/api/events/public/7/registrations", json=self.payload)
        self.assertEqual(response.status_code, 404)
        self.db.add.assert_not_called()
        self.db.close.assert_called_once()

    def test_registration_duplicate_rolls_back(self):
        self.db.commit.side_effect = FakeIntegrityError("Duplicate entry for key uq_event_training_registration_email")
        response = self.client.post("/api/events/public/7/registrations", json=self.payload)
        self.assertEqual(response.status_code, 409)
        self.db.rollback.assert_called_once()
        self.db.close.assert_called_once()

    def test_registration_unrelated_integrity_failure(self):
        self.db.commit.side_effect = FakeIntegrityError("Other database failure")
        with self.assertLogs(self.controller.logger, level="ERROR"):
            response = self.client.post("/api/events/public/7/registrations", json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.db.rollback.assert_called_once()
        self.db.close.assert_called_once()

    def test_registration_database_failure(self):
        self.db.commit.side_effect = RuntimeError("Database unavailable")
        with self.assertLogs(self.controller.logger, level="ERROR"):
            response = self.client.post("/api/events/public/7/registrations", json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.db.rollback.assert_called_once()
        self.db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
