# -*- coding: utf-8 -*-
"""Vercel serverless entry: Flask app를 WSGI 앱으로 노출."""
from app import app

# Vercel Python 런타임은 api/*.py 에서 app (WSGI) 변수를 찾아 실행합니다.
