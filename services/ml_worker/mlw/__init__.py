"""ML worker service — hosts scikit-learn model training + inference.

Runs as a separate Celery app so the api service stays lean and so the
scikit-learn / joblib / numpy footprint doesn't leak into the request
path. The api enqueues training tasks by name; the worker reads shared
DB rows (users, assets, price_bars, ml_*) via the api's SQLAlchemy
models over ``PYTHONPATH``.
"""
