#!/usr/bin/env python3
"""Send a real test SMS through the shared Mastercodes service.

Usage: bash scripts/run_send_test_sms.sh PHONE "Your test message"
Run with the project's installed requirements. Each invocation sends a new SMS.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public.controllers.sms_controller import SMSService


def main():
    if len(sys.argv) != 3:
        print('Usage: python scripts/send_test_sms.py PHONE "Your test message"')
        return 2
    result = SMSService.send_message(sys.argv[1], sys.argv[2], process_name='test_sms')
    print(result['message'])
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
