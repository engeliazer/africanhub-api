from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from auth.models.models import UserDevice
from auth.models.schemas import UserDeviceCreate
import json
from datetime import datetime


def normalize_device_fingerprint(fingerprint_data: dict) -> dict:
    """
    Accept FingerprintJS payloads where browser/os/hardware live under
    `components` or at the top level (frontend-enriched shape).
    """
    if not fingerprint_data or not isinstance(fingerprint_data, dict):
        raise ValueError("Device fingerprint must be a JSON object")

    data = dict(fingerprint_data)
    components = data.get("components") or {}
    if not isinstance(components, dict):
        components = {}

    def _component_value(key: str):
        block = components.get(key)
        if isinstance(block, dict) and "value" in block:
            return block.get("value")
        return None

    if not data.get("browser_info"):
        data["browser_info"] = components.get("browser_info") or {}
    if not data.get("os_info"):
        data["os_info"] = components.get("os_info") or {}
    if not data.get("hardware_info"):
        data["hardware_info"] = components.get("hardware_info") or {}

    browser_info = data["browser_info"]
    os_info = data["os_info"]
    hardware_info = data["hardware_info"]

    if not browser_info.get("name"):
        vendor_flavors = _component_value("vendorFlavors")
        if isinstance(vendor_flavors, list) and vendor_flavors:
            browser_info["name"] = str(vendor_flavors[0]).capitalize()
        elif components.get("vendor", {}).get("value"):
            browser_info["name"] = "Chrome"

    if not os_info.get("name"):
        platform = _component_value("platform")
        if platform:
            os_info["name"] = (
                "macOS" if platform == "MacIntel" else str(platform)
            )
        if not os_info.get("version"):
            os_info["version"] = "unknown"

    if not hardware_info:
        res = _component_value("screenResolution")
        hardware_info = {
            "screenResolution": f"{res[0]}x{res[1]}" if isinstance(res, list) and len(res) >= 2 else None,
            "colorDepth": _component_value("colorDepth"),
            "hardwareConcurrency": _component_value("hardwareConcurrency"),
            "deviceMemory": _component_value("deviceMemory"),
        }
        data["hardware_info"] = hardware_info

    components["browser_info"] = browser_info
    components["os_info"] = os_info
    components["hardware_info"] = hardware_info
    data["components"] = components
    return data


def parse_device_fingerprint_from_request(request) -> Optional[dict]:
    """Read device fingerprint from POST JSON, form, query, or JSON body on GET."""
    if request.is_json:
        body = request.get_json(silent=True) or {}
        fp = body.get("device_fingerprint")
        if fp:
            if isinstance(fp, str):
                fp = json.loads(fp)
            return normalize_device_fingerprint(fp)
        if body.get("visitorId"):
            return normalize_device_fingerprint(body)

    form_fp = request.form.get("device_fingerprint")
    if form_fp:
        parsed = json.loads(form_fp) if isinstance(form_fp, str) else form_fp
        return normalize_device_fingerprint(parsed)

    query_fp = request.args.get("device_fingerprint")
    if query_fp:
        parsed = json.loads(query_fp) if isinstance(query_fp, str) else query_fp
        return normalize_device_fingerprint(parsed)

    raw = request.get_data(as_text=True)
    if raw and raw.strip():
        try:
            body = json.loads(raw)
            fp = body.get("device_fingerprint") if isinstance(body, dict) else None
            if fp:
                if isinstance(fp, str):
                    fp = json.loads(fp)
                return normalize_device_fingerprint(fp)
            if isinstance(body, dict) and body.get("visitorId"):
                return normalize_device_fingerprint(body)
        except json.JSONDecodeError:
            pass

    return None


class DeviceFingerprintService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _as_user_id(user_id) -> int:
        return int(user_id)

    @staticmethod
    def _is_truthy_primary(value) -> bool:
        return value is True or value == 1 or value == "1"

    def get_or_create_device(
        self, user_id: int, fingerprint_data: dict, created_by: int
    ) -> Optional[UserDevice]:
        """
        Get or create a device record for the user.

        Same visitor_id may exist on different users (unique per user_id + visitor_id).
        """
        try:
            user_id = self._as_user_id(user_id)
            created_by = self._as_user_id(created_by)
            fingerprint_data = normalize_device_fingerprint(fingerprint_data)
            # Extract visitor ID from the correct location
            visitor_id = fingerprint_data.get('visitorId')
            
            if not visitor_id:
                raise ValueError("Visitor ID is required in fingerprint data")
            
            # Extract components from the correct location
            components = fingerprint_data.get('components', {})
            
            # Extract browser and OS information
            browser_info = components.get('browser_info', {})
            os_info = components.get('os_info', {})
            hardware_info = components.get('hardware_info', {})
            
            # Create security fingerprints object with more detailed information
            security_fingerprints = {
                'canvas': {
                    'text': components.get('canvas', {}).get('value', {}).get('text'),
                    'geometry': components.get('canvas', {}).get('value', {}).get('geometry'),
                    'winding': components.get('canvas', {}).get('value', {}).get('winding')
                },
                'audio': {
                    'value': components.get('audio', {}).get('value'),
                    'duration': components.get('audio', {}).get('duration')
                }
            }
            
            # Create device data with available fingerprint information
            device_data = {
                'user_id': user_id,
                'visitor_id': visitor_id,
                'browser_name': browser_info.get('name', 'unknown'),
                'browser_version': browser_info.get('version', 'unknown'),
                'os_name': os_info.get('name', 'unknown'),
                'os_version': os_info.get('version', 'unknown'),
                'hardware_info': hardware_info,  # Store as JSON
                'security_fingerprints': security_fingerprints,  # Store as JSON
                'is_primary': False,
                'last_used': datetime.utcnow(),
                'created_by': created_by,
                'updated_by': created_by
            }
            
            # Check if this visitor_id already exists for this user
            existing_device = self.db.query(UserDevice).filter(
                UserDevice.user_id == user_id,
                UserDevice.visitor_id == visitor_id,
                UserDevice.is_active == True
            ).first()
            
            if existing_device:
                # Update existing device with new fingerprint data
                try:
                    existing_device.last_used = datetime.utcnow()
                    existing_device.hardware_info = device_data['hardware_info']
                    existing_device.security_fingerprints = device_data['security_fingerprints']
                    existing_device.browser_version = device_data['browser_version']  # Update browser version
                    existing_device.updated_by = created_by
                    self.db.commit()
                    self.db.refresh(existing_device)
                    return existing_device
                except Exception as e:
                    # Handle concurrent update - refresh and retry
                    self.db.rollback()
                    self.db.refresh(existing_device)
                    existing_device.last_used = datetime.utcnow()
                    existing_device.updated_by = created_by
                    self.db.commit()
                    self.db.refresh(existing_device)
                    return existing_device
            
            # Create new device
            # Check if this is the user's first device - if so, make it primary
            # Use with_for_update to prevent race conditions when checking for first device
            existing_devices = self.db.query(UserDevice).filter(
                UserDevice.user_id == user_id,
                UserDevice.is_active == True
            ).with_for_update().all()
            
            # If this is the first device for this user, make it primary
            if len(existing_devices) == 0:
                device_data['is_primary'] = True
            
            try:
                new_device = UserDevice(**device_data)
                self.db.add(new_device)
                self.db.commit()
                self.db.refresh(new_device)
                return new_device
            except IntegrityError:
                self.db.rollback()
                existing_device = self.db.query(UserDevice).filter(
                    UserDevice.user_id == user_id,
                    UserDevice.visitor_id == visitor_id,
                    UserDevice.is_active == True,
                ).first()
                if existing_device:
                    self.db.refresh(existing_device)
                    return existing_device
                raise ValueError(
                    "Device registration blocked by database constraint on visitor_id. "
                    "Run migration user_devices_unique_per_user (alembic upgrade head)."
                ) from None

        except ValueError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to get or create device: {str(e)}") from e

    def get_device_access_status(self, user_id: int, visitor_id: str) -> Dict[str, Any]:
        """
        Decide if this browser may access materials and return diagnostics for the UI.
        """
        user_id = self._as_user_id(user_id)
        self.db.expire_all()

        device = self.db.query(UserDevice).filter(
            UserDevice.user_id == user_id,
            UserDevice.visitor_id == visitor_id,
            UserDevice.is_active == True,
        ).first()

        primary = self.db.query(UserDevice).filter(
            UserDevice.user_id == user_id,
            UserDevice.is_active == True,
            UserDevice.is_primary.is_(True),
        ).first()

        authorized = device is not None and self._is_truthy_primary(device.is_primary)

        reason = "authorized"
        if not device:
            reason = "device_not_registered_for_user"
        elif not self._is_truthy_primary(device.is_primary):
            if primary and primary.visitor_id != visitor_id:
                reason = "primary_is_another_device"
            else:
                reason = "device_not_primary"

        return {
            "is_authorized": authorized,
            "reason": reason,
            "request_visitor_id": visitor_id,
            "device_id": device.id if device else None,
            "device_is_primary": self._is_truthy_primary(device.is_primary) if device else False,
            "primary_device_id": primary.id if primary else None,
            "primary_visitor_id": primary.visitor_id if primary else None,
        }

    def check_device_access(self, user_id: int, visitor_id: str) -> bool:
        """True when this visitor_id is the user's primary device."""
        try:
            return self.get_device_access_status(user_id, visitor_id)["is_authorized"]
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Error checking device access: {str(e)}")

    def get_user_devices(self, user_id: int) -> List[UserDevice]:
        """Get all devices for a user"""
        try:
            devices = self.db.query(UserDevice).filter(
                UserDevice.user_id == user_id,
                UserDevice.is_active == True
            ).order_by(UserDevice.last_used.desc()).all()
            return devices
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Error getting user devices: {str(e)}")

    def update_device_status(self, device_id: int, is_primary: bool, updated_by: int) -> Optional[UserDevice]:
        """
        Update device primary status atomically to prevent race conditions
        """
        try:
            updated_by = self._as_user_id(updated_by)
            # Lock the device row to prevent concurrent modifications
            device = self.db.query(UserDevice).filter(
                UserDevice.id == device_id,
                UserDevice.is_active == True
            ).with_for_update().first()

            if not device:
                return None

            # If setting as primary, atomically unset all other devices for this user first
            if is_primary:
                # Use a single atomic UPDATE to set all other devices to non-primary
                self.db.query(UserDevice).filter(
                    UserDevice.user_id == device.user_id,
                    UserDevice.is_active == True,
                    UserDevice.id != device_id
                ).update({"is_primary": False}, synchronize_session=False)
                
                # Verify no other device is still primary (double-check with lock)
                other_primary = self.db.query(UserDevice).filter(
                    UserDevice.user_id == device.user_id,
                    UserDevice.is_active == True,
                    UserDevice.is_primary == True,
                    UserDevice.id != device_id
                ).with_for_update().first()
                
                if other_primary:
                    # Another device is still primary, rollback and fail
                    self.db.rollback()
                    raise ValueError("Another device is already primary. Please try again.")

            # Now safely set this device's status
            device.is_primary = is_primary
            device.updated_by = updated_by
            self.db.commit()
            self.db.refresh(device)
            return device
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to update device status: {str(e)}")

    def deactivate_device(self, device_id: int, user_id: int, updated_by: int) -> Optional[UserDevice]:
        """
        Deactivate a device
        """
        device = self.db.query(UserDevice).filter(
            UserDevice.id == device_id,
            UserDevice.user_id == user_id,
            UserDevice.is_active == True
        ).first()

        if not device:
            return None

        device.is_active = False
        device.updated_by = updated_by
        self.db.commit()
        self.db.refresh(device)
        return device 