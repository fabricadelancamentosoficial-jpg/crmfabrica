web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT --log-file -
release: python3 -c "from app import init_db; init_db()"
