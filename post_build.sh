#!/bin/bash
echo "=========================================="
echo "🚀 Running migrations on Render..."
echo "=========================================="

python manage.py makemigrations main
python manage.py migrate

echo "=========================================="
echo "✅ Migrations completed!"
echo "=========================================="