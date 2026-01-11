from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from auth.models.models import UserDevice
from auth.models.schemas import UserDeviceCreate
import json
from datetime import datetime

class DeviceFingerprintService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_device(self, user_id: int, fingerprint_data: dict, created_by: int) -> UserDevice:
        """Get or create a device record for the user"""
        try:
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
                'os_version': f"Macintosh; Intel Mac OS X {os_info.get('version', 'unknown')}" if os_info.get('name') == 'MacIntel' else os_info.get('version', 'unknown'),
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
                    return existing_device
                except Exception as e:
                    # Handle concurrent update - refresh and retry
                    self.db.rollback()
                    self.db.refresh(existing_device)
                    existing_device.last_used = datetime.utcnow()
                    existing_device.updated_by = created_by
                    self.db.commit()
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
                # Another request created this device concurrently (duplicate visitor_id)
                self.db.rollback()
                # Fetch the existing device by visitor_id (unique globally)
                existing_device = self.db.query(UserDevice).filter(
                    UserDevice.visitor_id == visitor_id,
                    UserDevice.is_active == True
                ).first()
                if existing_device:
                    return existing_device
                # If we still can't find it, re-raise for visibility
                raise
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to get or create device: {str(e)}")

    def check_device_access(self, user_id: int, visitor_id: str) -> bool:
        """
        Check if a device is allowed to access materials.
        Only returns True if the device is already marked as primary.
        Does NOT automatically promote devices to primary - that only happens during device creation.
        """
        try:
            # Check if this device exists
            device = self.db.query(UserDevice).filter(
                UserDevice.user_id == user_id,
                UserDevice.visitor_id == visitor_id,
                UserDevice.is_active == True
            ).first()
            
            if not device:
                return False
                
            # Only allow access if this device is already primary
            # If it's not primary, deny access (even if user has no primary device)
            # Primary status can only be set explicitly via update_device_status or during first device creation
            return device.is_primary
            
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