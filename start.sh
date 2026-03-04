#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
# O Railway precisa ouvir na porta $PORT
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
