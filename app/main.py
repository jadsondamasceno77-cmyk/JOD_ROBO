
@app.get('/')
def read_root():
    return {'message': 'FastAPI is running'}
