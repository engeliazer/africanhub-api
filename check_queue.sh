#!/bin/bash
# Quick queue check script

echo "🔍 Celery Queue Status Check"
echo "=========================="

# Check Redis queue
echo "📊 Queue Length:"
redis-cli LLEN video_processing

echo ""
echo "🔄 Active Workers:"
ps aux | grep celery | grep -v grep | wc -l

echo ""
echo "📋 Recent Logs:"
tail -5 celery.log

echo ""
echo "💾 Database Status:"
python3 -c "
import pymysql
try:
    conn = pymysql.connect(host='localhost', user='root', password='', database='ocpac', port=3306)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM subtopic_materials WHERE processing_status = \"processing\"')
    processing = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM subtopic_materials WHERE processing_status = \"completed\"')
    completed = cursor.fetchone()[0]
    print(f'   Processing: {processing}')
    print(f'   Completed: {completed}')
    conn.close()
except Exception as e:
    print(f'   Error: {e}')
"
