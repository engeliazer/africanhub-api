import unittest
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, Session
from public.services.sms_report_service import build_sms_report, parse_report_filters

Base = declarative_base()


class Audit(Base):
    __tablename__ = 'sms_logs'
    id = Column(Integer, primary_key=True)
    recipient = Column(String)
    recipient_name = Column(String)
    category = Column(String)
    batch_name = Column(String)
    status = Column(String)
    provider = Column(String, default='mastercodes')
    process_name = Column(String, default='api_send_batch')
    sms_count = Column(Integer)
    created_at = Column(DateTime)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.db.add_all([
            Audit(id=1, recipient='+255712345678', recipient_name='Hamis', category='bulk',
                  batch_name='Welcome', status='sent', sms_count=2, created_at=datetime(2026,11,20)),
            Audit(id=2, recipient='+255787654321', recipient_name='Asha', category='bulk',
                  batch_name='Welcome', status='failed', sms_count=1, created_at=datetime(2026,11,20,23,59,59,999999)),
            Audit(id=3, recipient='+255712345678', recipient_name='Hamis', category='single',
                  batch_name=None, status='sent', sms_count=1, created_at=datetime(2026,11,21)),
        ])
        self.db.commit()

    def report(self, **params):
        return build_sms_report(self.db, Audit, parse_report_filters(params))

    def test_inclusive_dates_totals_and_pagination(self):
        summary, rows, pages = self.report(from_date='2026-11-20', to_date='2026-11-20', per_page='1')
        self.assertEqual(summary, dict(total_messages=2, total_sms_count=3, sent=1, failed=1,
                                     unique_recipients=2, sent_sms_count=2, failed_sms_count=1))
        self.assertEqual([r.id for r in rows], [2])
        self.assertEqual(pages['total_pages'], 2)
        self.assertEqual(self.report(from_date='2026-11-20', to_date='2026-11-20', per_page='1', page='2')[1][0].id, 1)

    def test_combined_filters(self):
        summary, rows, _ = self.report(batch_name='Welcome', category='bulk', recipient_name='Ham',
                                      recipient='712', status='sent', provider='mastercodes', process_name='api_send_batch')
        self.assertEqual(summary['total_messages'], 1)
        self.assertEqual(rows[0].id, 1)

    def test_empty_and_literal_search(self):
        for params in ({'recipient_name': '%'}, {'batch_name': 'missing'}, {'recipient_name': '_'}):
            summary, rows, pages = self.report(**params)
            self.assertTrue(all(v == 0 for v in summary.values()))
            self.assertEqual(rows, [])
            self.assertEqual(pages['total_pages'], 0)

    def test_validation(self):
        for args in ({'category':'other'}, {'status':'delivered'}, {'from_date':'bad'},
                     {'from_date':'2026-11-21', 'to_date':'2026-11-20'}, {'page':'0'},
                     {'page':'abc'}, {'per_page':'-1'}, {'to_date':'9999-12-31'}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                parse_report_filters(args)
        self.assertEqual(parse_report_filters({'per_page':'500'})['per_page'], 100)


if __name__ == '__main__':
    unittest.main()
