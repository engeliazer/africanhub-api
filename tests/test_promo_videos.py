"""Promo video admin CRUD and public playback, with the database and VdoCipher mocked."""
import io
import sys
import types
import unittest
from datetime import datetime
from functools import wraps
from pathlib import Path
from unittest.mock import MagicMock, patch


def _install_missing_stubs():
    """Allow these tests to import when optional local packages are not installed."""
    if "dotenv" not in sys.modules:
        try:
            import dotenv  # noqa: F401
        except ModuleNotFoundError:
            dotenv = types.ModuleType("dotenv")
            dotenv.load_dotenv = lambda *args, **kwargs: False
            sys.modules["dotenv"] = dotenv

    if "flask_jwt_extended" not in sys.modules:
        try:
            import flask_jwt_extended  # noqa: F401
        except ModuleNotFoundError:
            jwt_mod = types.ModuleType("flask_jwt_extended")

            def jwt_required(*args, **kwargs):
                def decorator(fn):
                    @wraps(fn)
                    def wrapper(*fn_args, **fn_kwargs):
                        from flask import jsonify, request
                        if not request.headers.get("Authorization", "").startswith("Bearer "):
                            return jsonify({"msg": "Missing Authorization Header"}), 401
                        return fn(*fn_args, **fn_kwargs)
                    return wrapper
                return decorator

            jwt_mod.jwt_required = jwt_required
            jwt_mod.get_jwt_identity = lambda: "7"
            sys.modules["flask_jwt_extended"] = jwt_mod

    if "pydantic" not in sys.modules:
        try:
            import pydantic  # noqa: F401
        except ModuleNotFoundError:
            pydantic = types.ModuleType("pydantic")

            class ValidationError(Exception):
                def errors(self):
                    return [{"loc": ("body",), "msg": str(self)}]

            class BaseModel:
                def __init__(self, **data):
                    annotations = getattr(self.__class__, "__annotations__", {})
                    provided = set()
                    for name in annotations:
                        if name in data:
                            setattr(self, name, data[name])
                            provided.add(name)
                        elif name in self.__class__.__dict__:
                            setattr(self, name, self.__class__.__dict__[name])
                        else:
                            raise ValidationError(f"{name} is required")
                    self.__fields_set__ = provided

                def model_dump(self, exclude_unset=False):
                    names = self.__fields_set__ if exclude_unset else self.__class__.__annotations__
                    return {name: getattr(self, name) for name in names}

            pydantic.BaseModel = BaseModel
            pydantic.ValidationError = ValidationError
            sys.modules["pydantic"] = pydantic


def _import_controller():
    """Import the controller without executing database/__init__.py when MySQL is unavailable."""
    _install_missing_stubs()
    try:
        import pymysql  # noqa: F401
    except ModuleNotFoundError:
        database_mod = types.ModuleType("database")
        database_mod.__path__ = [str(Path(__file__).resolve().parents[1] / "database")]
        db_mod = types.ModuleType("database.db_connector")
        db_mod.get_db = lambda: None
        db_mod.DBConnector = object
        with patch.dict(sys.modules, {"database": database_mod, "database.db_connector": db_mod}):
            from promo_videos.controllers import promo_videos_controller as controller
            return controller
    from promo_videos.controllers import promo_videos_controller as controller
    return controller


from flask import Flask

controller = _import_controller()


def _video(**overrides):
    data = dict(
        id=3,
        title="How African Hub works",
        slug="how-african-hub-works",
        description="A short introduction",
        status="published",
        video_status="ready",
        vdocipher_video_id="secret-vdo-id",
        thumbnail_url="https://cdn.example/thumb.jpg",
        cover_url=None,
        video_duration=95,
        sort_order=1,
        created_by=1,
        updated_by=1,
        created_at=datetime(2026, 11, 20, 12, 0, 0),
        updated_at=datetime(2026, 11, 20, 12, 0, 0),
        deleted_at=None,
    )
    data.update(overrides)
    return type("Video", (), data)()


class Query:
    def __init__(self, first=None, rows=None):
        self._first = first
        self._rows = rows or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return list(self._rows)


class PromoVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = Flask(__name__)
        app.register_blueprint(controller.promo_videos_bp, url_prefix="/api")
        cls.app = app
        cls.client = app.test_client()
        cls.auth = {"Authorization": "Bearer test"}

    def setUp(self):
        self.db = MagicMock()
        self.db_patch = patch.object(controller, "get_db", return_value=self.db)
        self.service_patch = patch.object(controller, "get_promo_vdocipher_service")
        self.db_patch.start()
        self.service = self.service_patch.start()
        self.service.return_value = None

    def tearDown(self):
        self.db_patch.stop()
        self.service_patch.stop()

    def test_public_list_omits_provider_id(self):
        published = _video()
        self.db.query.return_value = Query(rows=[published])

        response = self.client.get("/api/promo-videos/public")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"][0]["slug"], "how-african-hub-works")
        self.assertNotIn("vdocipher_video_id", body["data"][0])
        self.assertNotIn("created_by", body["data"][0])

    def test_play_hides_unpublished_videos(self):
        self.db.query.return_value = Query(first=None)
        promo = MagicMock()
        self.service.return_value = promo

        response = self.client.post("/api/promo-videos/public/draft-video/play")

        self.assertEqual(response.status_code, 404)
        promo.generate_playback_otp.assert_not_called()

    def test_play_waits_until_video_is_ready(self):
        self.db.query.return_value = Query(first=_video(video_status="processing"))

        response = self.client.post("/api/promo-videos/public/how-african-hub-works/play")

        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.get_json()["video_status"], "processing")

    def test_play_mints_otp_with_promo_key_only(self):
        video = _video()
        self.db.query.return_value = Query(first=video)
        promo = MagicMock()
        promo.generate_playback_otp.return_value = {"otp": "otp-token", "playbackInfo": "playback"}
        self.service.return_value = promo

        response = self.client.post("/api/promo-videos/public/how-african-hub-works/play")

        self.assertEqual(response.status_code, 200)
        promo.generate_playback_otp.assert_called_once_with("secret-vdo-id")
        data = response.get_json()["data"]
        self.assertEqual(data["otp"], "otp-token")
        self.assertEqual(data["playbackInfo"], "playback")
        self.assertNotIn("vdocipher_video_id", data["video"])
        self.assertEqual(data["video"]["slug"], "how-african-hub-works")

    def test_create_requires_login(self):
        response = self.client.post("/api/promo-videos", json={"title": "Intro", "vdocipher_video_id": "abc"})
        self.assertEqual(response.status_code, 401)

    def test_create_slugifies_title_and_stores_vdocipher_status(self):
        self.db.query.return_value = Query(first=None)
        promo = MagicMock()
        promo.get_video_details.return_value = {
            "status": "ready",
            "length": 40,
            "thumbnail": "https://cdn.example/from-vdo.jpg",
        }
        self.service.return_value = promo

        def refresh(video):
            video.id = 9
            video.created_at = datetime(2026, 11, 20, 12, 0, 0)
            video.updated_at = datetime(2026, 11, 20, 12, 0, 0)

        self.db.refresh.side_effect = refresh

        response = self.client.post(
            "/api/promo-videos",
            json={"title": "How African Hub Works", "vdocipher_video_id": "abc123"},
            headers=self.auth,
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        saved = self.db.add.call_args[0][0]
        self.assertEqual(saved.slug, "how-african-hub-works")
        self.assertEqual(saved.vdocipher_video_id, "abc123")
        self.assertEqual(saved.video_status, "ready")
        self.assertEqual(saved.thumbnail_url, "https://cdn.example/from-vdo.jpg")
        self.assertEqual(saved.status, "draft")
        self.assertEqual(saved.created_by, 7)
        promo.get_video_details.assert_called_once_with("abc123")
        self.assertEqual(response.get_json()["data"]["vdocipher_video_id"], "abc123")

    def test_create_rejects_unknown_vdocipher_video(self):
        self.db.query.return_value = Query(first=None)
        promo = MagicMock()
        promo.get_video_details.side_effect = Exception("Video missing not found in VdoCipher")
        self.service.return_value = promo

        response = self.client.post(
            "/api/promo-videos",
            json={"title": "Missing", "vdocipher_video_id": "missing"},
            headers=self.auth,
        )

        self.assertEqual(response.status_code, 400)
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()

    def test_create_without_vdocipher_id_stays_pending(self):
        self.db.query.return_value = Query(first=None)
        promo = MagicMock()
        self.service.return_value = promo
        self.db.refresh.side_effect = lambda video: setattr(video, "id", 4)

        response = self.client.post(
            "/api/promo-videos",
            json={"title": "Coming soon", "video_status": "ready"},
            headers=self.auth,
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        saved = self.db.add.call_args[0][0]
        self.assertIsNone(saved.vdocipher_video_id)
        self.assertEqual(saved.video_status, "pending")
        promo.get_video_details.assert_not_called()

    def test_update_links_vdocipher_video_and_marks_it_ready(self):
        video = _video(vdocipher_video_id=None, video_status="pending")
        self.db.query.return_value = Query(first=video)
        promo = MagicMock()
        promo.get_video_details.return_value = {"status": "ready", "length": 30}
        self.service.return_value = promo

        response = self.client.put(
            "/api/promo-videos/3",
            json={"vdocipher_video_id": "abc123"},
            headers=self.auth,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(video.vdocipher_video_id, "abc123")
        self.assertEqual(video.video_status, "ready")
        promo.get_video_details.assert_called_once_with("abc123")

    def test_update_clears_vdocipher_link_and_returns_to_pending(self):
        video = _video()
        self.db.query.return_value = Query(first=video)

        response = self.client.put(
            "/api/promo-videos/3",
            json={"vdocipher_video_id": ""},
            headers=self.auth,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIsNone(video.vdocipher_video_id)
        self.assertEqual(video.video_status, "pending")

    def test_create_stores_optional_cover_without_replacing_provider_thumbnail(self):
        self.db.query.return_value = Query(first=None)
        self.db.refresh.side_effect = lambda video: setattr(video, "id", 9)

        with patch.object(controller, "save_promo_cover", return_value=("https://cdn.example/cover.png", None)):
            response = self.client.post(
                "/api/promo-videos",
                data={
                    "title": "How African Hub Works",
                    "vdocipher_video_id": "abc123",
                    "cover": (io.BytesIO(b"png"), "poster.png"),
                },
                content_type="multipart/form-data",
                headers=self.auth,
            )

        self.assertEqual(response.status_code, 201, response.get_json())
        saved = self.db.add.call_args[0][0]
        self.assertEqual(saved.cover_url, "https://cdn.example/cover.png")
        self.assertIsNone(saved.thumbnail_url)
        self.assertEqual(response.get_json()["data"]["cover_url"], "https://cdn.example/cover.png")

    def test_create_rejects_a_non_image_cover(self):
        self.db.query.return_value = Query(first=None)
        with patch.object(
            controller,
            "save_promo_cover",
            return_value=(None, "Cover must be a JPG, PNG, GIF, or WebP image"),
        ):
            response = self.client.post(
                "/api/promo-videos",
                data={
                    "title": "How African Hub Works",
                    "vdocipher_video_id": "abc123",
                    "cover": (io.BytesIO(b"%PDF"), "notes.pdf"),
                },
                content_type="multipart/form-data",
                headers=self.auth,
            )

        self.assertEqual(response.status_code, 400)
        self.db.add.assert_not_called()

    def test_update_replaces_cover(self):
        video = _video()
        self.db.query.return_value = Query(first=video)
        with patch.object(controller, "save_promo_cover", return_value=("https://cdn.example/new-cover.png", None)):
            response = self.client.put(
                "/api/promo-videos/3",
                data={"cover": (io.BytesIO(b"png"), "poster.png")},
                content_type="multipart/form-data",
                headers=self.auth,
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(video.cover_url, "https://cdn.example/new-cover.png")
        self.assertEqual(response.get_json()["data"]["cover_url"], "https://cdn.example/new-cover.png")


class PromoCoverFileTests(unittest.TestCase):
    def test_save_rejects_non_image(self):
        from werkzeug.datastructures import FileStorage

        from promo_videos.controllers.cover_utils import save_promo_cover

        stored = FileStorage(stream=io.BytesIO(b"%PDF"), filename="notes.pdf")
        url, error = save_promo_cover(stored)
        self.assertIsNone(url)
        self.assertEqual(error, "Cover must be a JPG, PNG, GIF, or WebP image")
