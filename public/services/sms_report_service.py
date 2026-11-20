"""Filtered SMS audit reporting. Stored timestamps and date filters use UTC."""
from datetime import datetime, timedelta
from sqlalchemy import case, func


def parse_report_filters(args):
    filters = {}
    for key in ('batch_name', 'category', 'recipient_name', 'recipient', 'status', 'process_name', 'provider'):
        value = (args.get(key) or '').strip()
        if value:
            filters[key] = value
    for key, allowed in (('category', ('single', 'bulk')), ('status', ('sent', 'failed'))):
        if key in filters and filters[key] not in allowed:
            raise ValueError('%s must be %s' % (key, ' or '.join(allowed)))
    for key in ('from_date', 'to_date'):
        value = (args.get(key) or '').strip()
        if value:
            try:
                filters[key] = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                raise ValueError('%s must be YYYY-MM-DD' % key)
    if filters.get('from_date') and filters.get('to_date') and filters['from_date'] > filters['to_date']:
        raise ValueError('from_date must be on or before to_date')
    if filters.get('to_date') == datetime(9999, 12, 31):
        raise ValueError('to_date must be before 9999-12-31')
    for key, default in (('page', 1), ('per_page', 20)):
        try:
            filters[key] = int(args.get(key, default))
        except (TypeError, ValueError):
            raise ValueError('%s must be a positive integer' % key)
        if filters[key] < 1:
            raise ValueError('%s must be a positive integer' % key)
    filters['per_page'] = min(100, filters['per_page'])
    return filters


def build_sms_report(db, model, filters):
    def apply(query):
        for key in ('category', 'batch_name', 'status', 'process_name', 'provider'):
            if key in filters:
                query = query.filter(getattr(model, key) == filters[key])
        for key in ('recipient_name', 'recipient'):
            if key in filters:
                query = query.filter(getattr(model, key).contains(filters[key], autoescape=True))
        if 'from_date' in filters:
            query = query.filter(model.created_at >= filters['from_date'])
        if 'to_date' in filters:
            query = query.filter(model.created_at < filters['to_date'] + timedelta(days=1))
        return query

    summary_row = apply(db.query(
        func.count(model.id), func.coalesce(func.sum(model.sms_count), 0),
        func.coalesce(func.sum(case((model.status == 'sent', 1), else_=0)), 0),
        func.coalesce(func.sum(case((model.status == 'failed', 1), else_=0)), 0),
        func.count(func.distinct(model.recipient)),
        func.coalesce(func.sum(case((model.status == 'sent', model.sms_count), else_=0)), 0),
        func.coalesce(func.sum(case((model.status == 'failed', model.sms_count), else_=0)), 0),
    )).one()
    keys = ('total_messages', 'total_sms_count', 'sent', 'failed', 'unique_recipients',
            'sent_sms_count', 'failed_sms_count')
    summary = dict(zip(keys, map(int, summary_row)))
    page, per_page = filters['page'], filters['per_page']
    rows = apply(db.query(model)).order_by(model.created_at.desc(), model.id.desc()).offset(
        (page - 1) * per_page).limit(per_page).all()
    return summary, rows, {'total': summary['total_messages'], 'page': page,
                          'per_page': per_page,
                          'total_pages': (summary['total_messages'] + per_page - 1) // per_page}
